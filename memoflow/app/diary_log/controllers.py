#!/usr/bin/env python
# coding=utf-8
# import asyncio
import logging
import json
from webob.exc import HTTPUnauthorized
# import time

from memoflow.conf import CONF
from memoflow.core import wsgi
from memoflow.core import dependency
from memoflow.utils.token_jwt import token_required
from memoflow.app.diary_log.common import GithubTablePathMap
from memoflow.app.diary_log.common import JianguoyunTablePathMap

from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
    Type,
)

LOG = logging.getLogger(__name__)

SYNC_DATA_BASE_PATH = CONF.diary_log['SYNC_DATA_BASE_PATH']
SYNC_TABLE_NAME = CONF.diary_log['SYNC_TABLE_NAME']
REVIEW_TABLE_NAME = CONF.diary_log['REVIEW_TABLE_NAME']

#clipboard
CLIPBOARD_TABLE_NAME = CONF.diary_log['CLIPBOARD_TABLE_NAME']  #clipboard数据表名
CLIPBOARD_DATA_BASE_PATH = CONF.diary_log[
    'DATA_BASE_CLIPBOARD_PATH']  #clipboard数据库路径

if CONF.diary_log['SEND_TO_GITHUB'] == True:
    sync_file_paths = GithubTablePathMap.sync_file_paths
    sync_table_names = GithubTablePathMap.sync_table_names
elif CONF.diary_log['SEND_TO_JIANGUOYUN'] == True:
    sync_file_paths = JianguoyunTablePathMap.sync_file_paths
    sync_table_names = JianguoyunTablePathMap.sync_table_names

@dependency.requires('diary_log_api')
# @dependency.requires('llm_api')
@dependency.requires('vector_db_api')
@dependency.requires('diary_db_api')
@dependency.requires('asyn_task_api')
class DiaryLog(wsgi.Application):
    def login(self, req):
        # 从请求中获取POST数据, 并转换为JSON格式
        data = json.loads(req.body)
        username = data.get('username')
        password = data.get('password')
        LOG.info(f"username: { username} password: *******")
        # 在这个简单例子中，用户名和密码匹配即可
        if (username == CONF.diary_log['DIARY_LOG_LOGIN_USER'] and
        password == CONF.diary_log['DIARY_LOG_LOGIN_PASSWORD']):
            user_id = 1  # 这里可以是从数据库中获取的用户ID1
            token = self.diary_log_api.generate_token(user_id)
            return json.dumps({"token": token})

        return json.dumps({"error": "Invalid credentials"}), 401     
        # return json.dumps({"content": processed_content})

    def add_log(self, req):
        # 从请求中获取POST数据
        data = req.body

        # 将POST数据转换为JSON格式
        diary_log = json.loads(data)
        LOG.info("diary_log json_data:, %s" % diary_log["content"][:70])

        # get tags
        tags = self.diary_log_api.get_tags_from_content(diary_log['content'])
        # 处理卡片笔记
        processed_content = self.diary_log_api.process_content(
            diary_log['content'])
        processed_block_content = self.diary_log_api.process_block(
            processed_content)

        # save que tags to vector db
        que_string: List[str] = self.diary_log_api.get_que_string_from_content(
            processed_block_content)
        if que_string:
            self.asyn_task_api.asyn_add_texts_to_vector_db_coll(texts=que_string,
                                                           metadatas=[{
                                                               "tags":
                                                               ','.join(tags)
                                                           }])
            # self.vector_db_api.add_texts(texts=que_string,
            #                              metadatas=[{"tags": ','.join(tags) }])

        # 保存到本地数据库
        record_id = self.diary_db_api.save_log(processed_block_content, tags)

        # # 发送到浮墨笔记
        # flomo_post_data = {"content": processed_content}
        # self.diary_log_api.send_log_flomo(flomo_post_data)

        # # 向notion 发送数据
        # self.asyn_task_api.celery_send_log_notion(diary_log=processed_content)
        # # asyncio.run(self.diary_log_api.run_tasks(diary_log))

        # 向github仓库（logseq 笔记软件）发送数据
        if CONF.diary_log['SEND_TO_GITHUB'] == True:
            file_path = CONF.diary_log['GITHUB_CURRENT_SYNC_FILE_PATH']
            commit_message = "commit by memoflow"
            branch_name = "main"
            token = CONF.diary_log['GITHUB_TOKEN']
            repo = CONF.diary_log['GITHUB_REPO']
            added_content = processed_block_content
            self.asyn_task_api.celery_update_file_to_github(
                token, repo, file_path, added_content, commit_message,
                branch_name)

        # 向坚果云发送异步任务，更新文件
        # 坚果云账号
        if CONF.diary_log['SEND_TO_JIANGUOYUN'] == True:
            JIANGUOYUN_COUNT = CONF.api_conf.JIANGUOYUN_COUNT
            JIANGUOYUN_TOKEN = CONF.api_conf.JIANGUOYUN_TOKEN
            base_url = CONF.api_conf.base_url
            to_path = CONF.api_conf.JIANGUOYUN_CURRENT_SYNC_FILE_PATH
            added_content = processed_block_content
            self.asyn_task_api.celery_update_file_to_jianguoyun(
                base_url,
                JIANGUOYUN_COUNT,
                JIANGUOYUN_TOKEN,
                to_path,
                added_content,
                overwrite=True)

        return json.dumps({"record_id": record_id, "content": processed_block_content})
        # return Response(json_data)

    @token_required
    def get_logs(self, req):
        pages = []
        contents = []
        ids = []
        for table_name in sync_table_names:
            temp_rows = self.diary_db_api.get_logs(
                table=table_name, columns=['content','id'])
            if temp_rows:
                pages.append(temp_rows)
        # rows = self.diary_db_api.get_logs(columns=['content','id'])
        pages.reverse()
        for page in pages:
            contents.extend([row[0] for row in page])
            ids.extend([row[1] for row in page])
        return json.dumps({'logs': contents, 'ids': ids})
    
    @token_required
    def update_log(self, req):
        # 从请求中获取POST数据
        data = req.body

        # 将POST数据转换为JSON格式
        diary_log = json.loads(data)
        LOG.info("diary_log json_data:, %s" % diary_log["content"][:70])

        # get tags
        tags = self.diary_log_api.get_tags_from_content(diary_log['content'])
        # 处理卡片笔记
        processed_content = self.diary_log_api.process_content(
            diary_log['content'])
        processed_block_content = self.diary_log_api.process_block(
            processed_content)
        diary_of_id = self.diary_db_api.get_log_by_id(diary_log["record_id"])

        if CONF.diary_log['SEND_TO_GITHUB'] == True:
            table_name = GithubTablePathMap.current_table_name
            table_path_of_repo = GithubTablePathMap.current_table_path
            other_table_path_map = GithubTablePathMap.other_table_path_map
        elif CONF.diary_log['SEND_TO_JIANGUOYUN'] == True:
            table_name = JianguoyunTablePathMap.current_table_name
            table_path_of_repo = JianguoyunTablePathMap.current_table_path
            other_table_path_map = JianguoyunTablePathMap.other_table_path_map

        if not diary_of_id:
            for other_table_name in other_table_path_map.keys():
                diary_of_id = self.diary_db_api.get_log_by_id(
                                        diary_log["record_id"],
                                        table_name=other_table_name)
                if diary_of_id:
                    table_name = other_table_name
                    table_path_of_repo = other_table_path_map[other_table_name]
                    break
            if not diary_of_id:
                return json.dumps({"error": "diary not found in database"})
        que_string: List[str] = self.diary_log_api.get_que_string_from_content(
            processed_block_content)
        if que_string and que_string[0] not in diary_of_id[0]:
            self.asyn_task_api.asyn_add_texts_to_vector_db_coll(texts=que_string,
                                                           metadatas=[{
                                                               "tags":
                                                               ','.join(tags)
                                                           }])
        # 保存到本地数据库
        self.diary_db_api.update_log(diary_log["record_id"], 
                                     processed_block_content,
                                     tags,
                                     table_name=table_name)

        rows = self.diary_db_api.get_logs(table=table_name)
        updated_contents = [row[0] for row in rows]
        updated_contents.reverse()
        updated_content = "\n".join(updated_contents)

        # 向github仓库（logseq 笔记软件）发送更新后的数据
        if CONF.diary_log['SEND_TO_GITHUB'] == True:
            file_path = table_path_of_repo
            commit_message = "commit by memoflow"
            branch_name = "main"
            token = CONF.diary_log['GITHUB_TOKEN']
            repo = CONF.diary_log['GITHUB_REPO']

            self.asyn_task_api.celery_push_updatedfile_to_github(
                token, repo, file_path, updated_content, commit_message,
                branch_name)
        elif CONF.diary_log['SEND_TO_JIANGUOYUN'] == True:
            JIANGUOYUN_COUNT = CONF.api_conf.JIANGUOYUN_COUNT
            JIANGUOYUN_TOKEN = CONF.api_conf.JIANGUOYUN_TOKEN
            base_url = CONF.api_conf.base_url
            to_path = table_path_of_repo
            # added_content = processed_block_content
            self.asyn_task_api.celery_push_updatedfile_to_jianguoyun(
                base_url,
                JIANGUOYUN_COUNT,
                JIANGUOYUN_TOKEN,
                to_path,
                updated_content,
                overwrite=True)
        return json.dumps({"content": processed_block_content})
                                                        
    @token_required
    def delete_log(self, req, record_id):
        res = self.diary_db_api.delete_log(record_id)
        if res:
            LOG.info(f"delete diary log success, id: {record_id}")
        rows = self.diary_db_api.get_logs()
        updated_contents = [row[0] for row in rows]
        updated_contents.reverse()

        # 向github仓库（logseq 笔记软件）发送更新后的数据
        if CONF.diary_log['SEND_TO_GITHUB'] == True:
            updated_content = "\n".join(updated_contents)

            file_path = CONF.diary_log['GITHUB_CURRENT_SYNC_FILE_PATH']
            commit_message = "commit by memoflow"
            branch_name = "main"
            token = CONF.diary_log['GITHUB_TOKEN']
            repo = CONF.diary_log['GITHUB_REPO']

            self.asyn_task_api.celery_push_updatedfile_to_github(
                token, repo, file_path, updated_content, commit_message,
                branch_name)

    def delete_all_log(self, req):
        return self.diary_db_api.delete_all_log()

    def test_flomo(self, req):
        self.diary_log_api.test_post_flomo()
        return "sucess"

    # review
    @token_required
    def get_review_logs(self, req):
        return self.diary_db_api.get_review_logs(
            table=REVIEW_TABLE_NAME,
            columns=['content'],
            data_base_path=SYNC_DATA_BASE_PATH)

    @token_required
    def delete_all_review_log(self, req):
        return self.diary_db_api.delete_all_review_log(
            data_base_path=SYNC_DATA_BASE_PATH, table=REVIEW_TABLE_NAME)

    # clipboard
    @token_required
    def get_clipboard_logs(self, req):
        return self.diary_db_api.get_clipboard_logs(
            table_name=CLIPBOARD_TABLE_NAME,
            columns=['content'],
            data_base_path=CLIPBOARD_DATA_BASE_PATH)

    def clipboard_addlog(self, req):
        # 从请求中获取POST数据
        data = req.body
        # 将POST数据转换为JSON格式
        diary_log = json.loads(data)
        LOG.info("diary_log json_data:, %s" % diary_log["content"][:70])
        # 保存到本地数据库
        self.diary_db_api.save_log_to_clipboard_table(
            table_name=CLIPBOARD_TABLE_NAME,
            columns=['content'],
            data=[diary_log["content"]],
            data_base_path=CLIPBOARD_DATA_BASE_PATH)
        return json.dumps(diary_log)  # data 是否可行？

    @token_required
    def get_contents_from_github(self, req):
        if CONF.diary_log['SEND_TO_GITHUB'] != True:
            return json.dumps({"error": "CONF SEND_TO_GITHUB != True"})
        if len(sync_file_paths) != len(sync_table_names):
            raise Exception("sync_file_paths and sync_table_names length not equal")
        token = CONF.diary_log['GITHUB_TOKEN']
        repo = CONF.diary_log['GITHUB_REPO']
        branch_name = "main"
        contents = self.diary_log_api.get_contents_from_github(
            token, repo, sync_file_paths, branch_name)
        if len(contents) != len(sync_file_paths):
            raise Exception("contents length and len(sync_file_paths) not equal")
        result = []
        for content in contents:
            result.extend(content)
        # return contents
        return json.dumps({"contents": result})

    @token_required
    def sync_contents_from_repo_to_db(self, req):
        if CONF.diary_log['SEND_TO_GITHUB'] == True:
            sync_file_paths = GithubTablePathMap.sync_file_paths
            sync_table_names = GithubTablePathMap.sync_table_names
            self.diary_log_api.sync_contents_from_github_to_db(
                sync_file_paths=sync_file_paths,
                sync_table_names=sync_table_names)
        elif CONF.diary_log['SEND_TO_JIANGUOYUN'] == True:
            self.diary_log_api.sync_contents_from_jianguoyun_to_db(
                sync_file_paths=JianguoyunTablePathMap.sync_file_paths,
                sync_table_names=JianguoyunTablePathMap.sync_table_names)

        return "success"

    def search_contents_from_vecter_db(self, req):
        data = req.body
        # 将POST数据转换为JSON格式
        search_data = json.loads(data)['search_data']
        LOG.info("search_data json_data:, %s" % search_data)
        # search contents from vecter db
        search_result = []
        if search_data:
            search_result = self.vector_db_api.search_texts(
                query=search_data, top_k=10)
        return json.dumps({"search_result": search_result})

    @token_required
    def update_all_que_to_vector_db(self, req):
        # get logs and send all que string to vector db
        log_list = self.diary_db_api.get_all_logs(
            table=SYNC_TABLE_NAME,
            columns=['id', 'content', 'tags'],
            data_base_path=SYNC_DATA_BASE_PATH)

        contents = [log[1] for log in log_list]
        index, que_list = self.diary_log_api.get_all_que_from_contents(
            contents)
        slice_log_list = [log_list[i] for i in index]
        tags = [log[2] for log in slice_log_list]
        # convert id into str
        ids = [str(log[0]) for log in slice_log_list]

        # all_ids = self.vector_db_api.get_vector_db_coll_all_ids().get('ids', None)
        # LOG.info("length of all_ids: %s" % len(all_ids))
        # # delete all ids
        # if all_ids:
        #     self.vector_db_api.delete_items_by_ids(ids=all_ids)

        # delete vector db collection all itmes
        self.vector_db_api.rm_coll_all_itmes()

        self.vector_db_api.add_texts(texts=que_list,
                                     metadatas=[{
                                         "tag": tag,
                                         "id": id
                                     } for tag, id in zip(tags, ids)])

        return "success"

    def peek_vector_db(self, req, limit):
        # peek vector db
        result_object = self.vector_db_api.peek_collection(limit=int(limit))
        result = {
            "ids": result_object.get('ids', None),
            "embeddings": result_object.get('embeddings', None),
            "metadatas": result_object.get('metadatas', None)
        }
        return json.dumps(result)

    def get_collection_items(self, req, limit: str):
        result_object = self.vector_db_api.get_collection_items(
            limit=int(limit))
        result = {
            "ids": result_object.get('ids', None),
            "embeddings": result_object.get('embeddings', None),
            "metadatas": result_object.get('metadatas', None)
        }
        return json.dumps(result)

    def get_vector_db_coll_all_ids(self, req):
        result_object = self.vector_db_api.get_vector_db_coll_all_ids()
        collection_size = self.vector_db_api.get_collection_size()
        result = {
            "ids": result_object.get('ids', None),
            "collection_size": collection_size
        }
        return json.dumps(result)

    @token_required
    def delete_collection_item(self, req):
        data = req.body
        # 将POST数据转换为JSON格式, ids 是列表
        ids: List = json.loads(data).get('ids', None)
        LOG.info("delete_data json_data:, %s" % ids)
        # delete collection item
        self.vector_db_api.delete_items_by_ids(ids=ids)
        return "success"

    @token_required
    def delete_all_collection_item(self, req):
        all_collection_ids: List = self.vector_db_api.get_vector_db_coll_all_ids().get(
            'ids', None)
        if all_collection_ids:
            self.vector_db_api.delete_items_by_ids(ids=all_collection_ids)
        return "success"
