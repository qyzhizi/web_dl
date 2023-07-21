# 使用 Python 3.10 镜像作为基础镜像
FROM python:3.9-slim

# RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list \
#     && apt-get update \
#     && apt-get install -y  git --fix-missing

RUN apt-get update \
    && apt-get install -y git --fix-missing

# 将工作目录设置为 /app
WORKDIR /app

# 将当前目录下的所有文件复制到 /app
COPY . /app


# RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip install --no-cache-dir -r requirements.txt

# 暴露容器的端口
EXPOSE 9000

# 给 run.sh 文件添加可执行权限
RUN chmod +x memoflow/cmd/run.sh

# 运行脚本
CMD ["bash", "-c", "memoflow/cmd/run.sh"]
