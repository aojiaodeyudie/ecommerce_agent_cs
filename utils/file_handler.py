import os
import hashlib
from utils.logger_handler import logger
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader,TextLoader


def get_file_md5_hex(file_path):#获取文件md5值，十六进制

    if not os.path.exists(file_path):
        logger.error(f"文件不存在：{file_path}")
        return

    if not os.path.isfile(file_path):
        logger.error(f"这不是一个文件：{file_path}")
        return

    md5_obj = hashlib.md5()
    chunk_size = 4096             #4K,避免大文件占用过多内存
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(chunk_size): #避免二进制读取
                md5_obj.update(chunk)
            return md5_obj.hexdigest()  # 返回md5值，十六进制字符串表示
    except Exception as e:
        logger.error(f"获取文件md5值出错：{e}")
        return None


def listdir_with_allowed_type(dir_path, allowed_types:tuple[str]):#返回目录下指定类型文件列表（允许的）
    files =[]
    if not os.path.isdir(dir_path):
        logger.error(f"目录不存在：{dir_path}")
        return files
    for file in os.listdir(dir_path):
        if file.endswith(allowed_types):
            files.append(os.path.join(dir_path, file))
    return tuple(files)

def pdf_loader(file_path,password=None) -> list[Document]:
    return PyPDFLoader(file_path,password).load()

def txt_loader(file_path, encoding="utf-8") -> list[Document]:
    return TextLoader(file_path, encoding="utf_8" ).load()
