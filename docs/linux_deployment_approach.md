## linux 环境非docker部署
- 1、环境准备
    - 一个linux环境
    - 安装依赖:
    pip install -r requirements.txt
    - 安装 redis: 
    安装方法, @todo

- 2、拉取代码，并修改配置文件`.env`
    ```
    git pull git@github.com:qyzhizi/memoflow.git
    ```
    与docker-compose.yml部署相比，这里只有CELERY_BROKER_URL 与CELERY_RESULT_BACKEND 的配置改变了。
    ```
    CELERY_BROKER_URL=redis://localhost:6379
    CELERY_RESULT_BACKEND=redis://localhost:6379

    # 发送到github仓库
    #github token, @todo 如何获取token
    GITHUB_TOKEN=xxxx
    GITHUB_REPO=github用户名/仓库名
    #仓库文件路径,相对仓库的根目录，例如：xxxx/demo.md
    GITHUB_CURRENT_SYNC_FILE_PATH=xxxx/demo.md

    # 发送到坚果云
    # 坚果云账号，例如：你的坚果云邮箱
    JIANGUOYUN_COUNT=坚果云账号
    # 坚果云api token
    JIANGUOYUN_TOKEN=xxxx
    # 文件路径,从根目录/开始
    JIANGUOYUN_TO_PATH=/xxxx/demo.md

    # 发送github仓库任务标志位， 如果不需要发送，设置为0
    SEND_TO_JIANGUOYUN=1
    # 发送坚果云任务标志位， 如果不需要发送，设置为0
    SEND_TO_GITHUB=1
    ```
- 3、启动
    ```
    cd memoflow/memoflow/cmd
    python3 main.py &
    ```

- 4、访问log笔记页面

    浏览器输入：http://x.x.x.x:9000/v1/diary-log/index.html

    本地访问：http://localhost:9000/v1/diary-log/index.html