# -*- coding: utf-8 -*-
"""
@Time ： 2022/12/18 15:41
@Auth ： zqzess
@File ：main.py
@FileDesc ：
@IDE ：PyCharm
@Motto：So long as it is for my ideal,I wouldn't regret dying for it a thousand times.
"""
import json
import os
import re
import sys
import threading
import time
import urllib
import ssl

import requests
from multiprocessing import Process, Queue, Manager

isDebug = True
jsonPath = '../sources.json'
# nowPath = ''
resourcePath = '../resources.txt'
readMePath = '../../../README.md'


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


# 日志输出
def printLog(log, color=''):
    global isDebug
    if isDebug:
        if color == 'red' or color == 'failed' or color == 'fail' or color == 'error':
            print(f"\n{bcolors.FAIL} {log} {bcolors.FAIL}\n")
        elif color == 'blue':
            print(f"{bcolors.OKBLUE} {log} {bcolors.OKBLUE}")
        elif color == 'pink':
            print(f"{bcolors.HEADER} {log} {bcolors.HEADER}")
        elif color == 'green' or color == 'success':
            print(f"{bcolors.OKGREEN} {log} {bcolors.OKGREEN}")
        elif color == 'yellow' or color == 'warn':
            print(f"\n{bcolors.WARNING} {log} {bcolors.WARNING}\n")
        elif color == 'lightblue':
            print(f"{bcolors.OKCYAN} {log} {bcolors.OKCYAN}")
        else:
            print(f"{bcolors.ENDC} {log} {bcolors.ENDC}")


# 关键字检索
def checkxbsName(name):
    isDrop = False
    list = ['书源合集', '整合', '交流群', '测试', 'beta', 'QQ频道', 'QQ群', '模版', '例子', '示例', 'Beta', 'BETA']
    for value in list:
        if re.search(value, name):
            printLog('发现关键词: ' + name + '  , 丢弃', 'warn')
            isDrop = True
    return isDrop


# 启动入口
def startWork():
    new_list = readRepoFromJson()
    process = []
    if os.path.exists(resourcePath):
        os.remove(resourcePath)
        print(resourcePath + '文件存在，已执行删除')
    for i in new_list:
        user = i[0]
        repo = i[1]  # 仓库链接
        srcUrl = i[2]  # 资源链接
        nowPath = '../repo/' + user + '/'  # 路径拼接，../repo/zqzess

        if user == 'jumpli':
            # 改作者仓库疑似搬运，跳过
            continue
        if user == 'zqzess' or user == '' or user == 'ThorJsbox' or user == 'TinhoXu':
            continue
        # 检查是否存在该用户仓库存放文件夹
        if not os.path.exists(nowPath):
            printLog(user + '仓库文件夹不存在', 'warn')
            os.makedirs(nowPath)
            if os.path.exists(nowPath):
                printLog(user + '仓库文件夹创建成功', 'success')
            else:
                printLog(user + '仓库文件夹创建失败', 'fail')
                break
        # process.append(Process(target=parseResouece, args=[nowPath, user, repo, srcUrl.strip()]))
        if isinstance(srcUrl, list):
            # 判断资源链接变量是字符串还是列表
            for i in srcUrl:
                process.append(Process(target=parseResouece, args=[nowPath, user, repo, i.strip()]))
        elif isinstance(srcUrl, str):
            process.append(Process(target=parseResouece, args=[nowPath, user, repo, srcUrl.strip()]))
    # 创建并启动进程
    [p.start() for p in process]
    # 等待子进程结束后再继续往下运行，在当前位置阻塞主进程
    [p.join() for p in process]


def readRepoFromJson():
    with open(jsonPath, encoding='utf-8') as f:
        result = json.load(f)
        # 定义一个空数组
        new_list = []
        for i in result:
            # i是个字典
            # [
            #   {
            #     "user": "xiaohucode",
            #     "repo": "https://github.com/xiaohucode/xiangse",
            #     "sourceurl": "https://github.com/xiaohucode/xiangse/blob/main/README.md"
            #   }
            # ]
            new_list.append((i.get('user'), i.get('repo'), i.get('sourceurl')))  # 将获取的值存入数组中
        # printLog(new_list)
        return new_list


def urlChangeToRaw(srcUrl):
    if re.search('github\.com', srcUrl, flags=0):
        # 将github链接置换成raw链接
        printLog('发现github链接: ' + srcUrl + '，将github链接置换为githubusercontent')
        srcUrl = srcUrl.replace('github', 'raw.githubusercontent').replace('/blob', '')
        printLog('置换后的链接: ' + srcUrl)
        return srcUrl
    elif re.search('jsdelivr\.net', srcUrl):
        return srcUrl


def parseResouece(nowPath, user, repo, srcUrl):
    # 进程锁
    manager = Manager()
    lock = manager.Lock()

    # 检查资源链接是xbs整合还是readme.md，如果是xbs则时间下载，如果是md则解析
    if re.search('\.xbs', srcUrl):
        srcUrl = urlChangeToRaw(srcUrl)
        printLog('资源链接是xbs文件: ' + srcUrl, 'red')
        writeSourcesListLock(lock, srcUrl)
        downloadResource(nowPath, srcUrl.strip())
    elif re.search('\.md', srcUrl) or re.search('\.txt', srcUrl) or re.search('\.conf', srcUrl):
        srcUrl = urlChangeToRaw(srcUrl)
        getResource(lock, nowPath, srcUrl.strip())
    else:
        # 既不是xbs也不是md，单纯一个github仓库链接
        getHtmlResource(lock, nowPath, user, repo, srcUrl)
    # 最后更新readme时间
    updateDate()


# 解析md资源
def getResource(lock, path, srcUrl):
    success = False  # 是否成功
    try_times = 0  # 重试次数
    res = None  # 返回值
    # 获取srcUrl链接资源
    while try_times < 5 and not success:
        res = requests.get(srcUrl)
        if res.status_code != 200:
            time.sleep(1)
            try_times = try_times + 1
        else:
            success = True
            break
    if not success:
        sys.exit('error in request %s\n\treturn code: %d' % (srcUrl, res.status_code))

    # 检索是否文件内是否存在xbs链接
    xbsList = re.findall('.+\.xbs', res.text)
    if xbsList:
        for url in xbsList:
            # tmp = url.split('/')
            # outpath = path + tmp[len(tmp) - 1]
            writeSourcesListLock(lock, url)
            # 启用多线程下载
            threading.Thread(target=downloadResource, args=(path, url)).start()


# 解析html资源
def getHtmlResource(lock, path, user, repo, srcUrl):
    repoApiUrl = 'https://api.github.com/repos/' + user + '/' + repo + '/contents'
    reponse = requests.get(repoApiUrl).json()
    if reponse:
        for i in reponse:
            name = i.get('name')
            srcUrl = i.get('download_url')
            if checkxbsName(name):
                continue
            elif re.search('\.xbs', name):
                writeSourcesListLock(lock, srcUrl)
                downloadResource(path, srcUrl)
            elif re.search('\.md', name):
                printLog('发现markdown文件: ' + name)


def downloadResource(path, srcUrl):
    tmpList = srcUrl.split('/')
    tmp = tmpList[len(tmpList) - 1]
    if re.search('%', tmp):
        printLog('发现非法字符%，进行urldecode\t\t' + tmp, 'warn')
        tmp = urllib.parse.unquote(tmp)
    if not checkxbsName(tmp):
        path = path + tmp
        printLog('开始下载： ' + srcUrl.strip())
        ssl._create_default_https_context = ssl._create_unverified_context
        index = 0
        while True:
            try:
                urllib.request.urlretrieve(srcUrl, path)
                index += 1
                # urllib.request.urlretrieve(srcUrl, path, download_progress_hook)
            except Exception as e:
                printLog(srcUrl + '  下载出错,重试', 'warn')
                if index > 5:
                    printLog('已重试达到最大次数，停止！', 'error')
                    break
                time.sleep(1)
                continue
            break
        printLog('下载成功：' + path, 'success')


def downloadResource2(path, srcUrl):
    # 下载速度似乎会更快一点,但是会有奇怪的错误
    tmpList = srcUrl.split('/')
    tmp = tmpList[len(tmpList) - 1]
    if re.search('%', tmp):
        printLog('发现非法字符，进行urldecode', 'warn')
        tmp = urllib.parse.unquote(tmp)
    if not checkxbsName(tmp):
        path = path + tmp
        printLog('开始下载： ' + srcUrl.strip())
        ssl._create_default_https_context = ssl._create_unverified_context
        index = 0
        while True:
            try:
                r = requests.get(srcUrl, stream=True)
                with open(path, 'wb') as f:
                    for ch in r:
                        f.write(ch)
                f.close()
                index += 1
            except Exception as e:
                printLog(srcUrl + ' 下载出错,重试', 'warn')
                if index > 5:
                    printLog('已重试达到最大次数，停止！', 'error')
                time.sleep(1)
                continue
            break
        printLog('下载成功：' + path, 'success')


def download_progress_hook(blocknum, blocksize, totalsize):
    """
    * 用于urllib.request.urlretrieve方法的回调函数，显示下载进度
    @ blocknum:当前已经下载的块
    @ blocksize:每次传输的块大小
    @ totalsize:网页文件总大小
    """
    if totalsize == 0:
        percent = 0
    else:
        percent = blocknum * blocksize / totalsize
    if percent > 1.0:
        percent = 1.0
    percent = percent * 100
    # 打印下载的百分比
    printLog("download %s : %.4f%%" % (percent), 'pink')


# 把xbs链接写入文件，带有进程锁
def writeSourcesListLock(lock, srcUrl):
    global resourcePath
    lock.acquire()
    with open(resourcePath, 'a+', encoding="UTF-8") as f:
        f.write(srcUrl.strip() + '\n')
        f.flush()
    f.close()
    lock.release()


def writeSourcesList(srcUrl):
    global resourcePath
    with open(resourcePath, 'a+', encoding="UTF-8") as f:
        f.write(srcUrl.strip() + '\n')
        f.flush()
    f.close()


def updateDate():
    text_list = []
    dateNow = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
    with open(readMePath, 'r', encoding="UTF-8") as f:
        for lineTmp in f.readlines():
            if re.search('自动更新时间', lineTmp):
                lineTmp = '**自动更新时间** ' + dateNow + '\n'
                text_list.append(lineTmp)
            else:
                text_list.append(lineTmp)
        f.flush()
        f.close()
    with open(readMePath, 'w+', encoding="UTF-8") as f2:
        for text in text_list:
            f2.write(text)
        f2.flush()
        f.close()


if __name__ == '__main__':
    startWork()
