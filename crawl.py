#!/usr/bin/env python2.7
#-*- coding:utf-8 -*-
import re,time
try:
    import json
except:
    import simplejson as json
from bs4 import BeautifulSoup
import urllib2

import requests
import redis
from scrapy import log

#redisdb = ('127.0.0.1', 6379, 'password', 0)
redisdb = ('127.0.0.1', 6379, '', 0)

def main():
    url = 'http://cn-proxy.com/'
    serv= CrawlVpnService()
    #serv.download_parse(url)

    #http://proxy.com.ru/list_2.html
    #serv.download_proxy_ru()

    #http://www.xici.net.co/nt/1
    #serv.download_proxy_pachong()

    #http://www.xici.net.co/nt/
    serv.download_proxy_xici()

    #update vpn
    serv.update_vpn()

class CrawlVpnService(object):
    """
    website: cn-proxy.com
    """
    def __init__(self):
        self.redis = redis.Redis(host=redisdb[0], 
                                 port=redisdb[1],
                                 password=redisdb[2],
                                 db=redisdb[3])
        self.count = self.redis.llen('vpn')

    def check_proxy_ip(self,ip, port):
       proxy_handler = urllib2.ProxyHandler({'http':'http://%s:%s'%(ip,str(port))})
       opener = urllib2.build_opener(proxy_handler)

       urllib2.install_opener(opener)
       header = {'Accept-Charset':'GBK,utf-8;q=0.7,*;q=0.3','User-Agent' : 'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US) AppleWebKit/534.16 (KHTML, like Gecko) Chrome/10.0.648.151 Safari/534.16'}
       try:
           request = urllib2.Request(url='https://www.baidu.com', headers = header)
           res = urllib2.urlopen(request, timeout=10)
           res.close()
           return res.code
       except Exception as msg:
           return 403

    def reckon_port(self, content, port):
        items = re.findall('>(var .*);<', content)
        if not items:
            return 0

        for item in items[0].split(';'):
            exec(item.replace('var', '').strip())
        port = eval(port)
        return port

    def download_proxy_pachong(self):
        links = [
                 'http://pachong.org/transparent.html',
                 'http://pachong.org/anonymous.html',
                 'http://pachong.org/high.html',
                 #'http://pachong.org/',
                 #'http://pachong.org/area/short/name/cn.html',
                 #'http://pachong.org/area/city/name/%E4%B8%AD%E5%9B%BD.html',
                 #'http://pachong.org/area/city/name/%E5%8C%97%E4%BA%AC.html',
                 #'http://pachong.org/area/city/name/%E5%8C%97%E4%BA%AC%E5%B8%82.html'
                ]
        for link in links:
            print link 
            response = requests.get(link, timeout=5)
            print time.strftime('%Y-%m-%d %H:%M:%S  ', time.localtime()), link 
            if response.status_code == 200:
                bs = BeautifulSoup(response.content)
                items = bs.find_all('tr')
                for tr in items:
                    infos = tr.find_all('td')
                    try:
                        ip = re.findall('\d+\.\d+\.\d+\.\d+', infos[1].string)
                    except:
                        continue

                    if not ip:
                        continue

                    port = re.findall('\((.*)\);', infos[2].string)
                    try:
                        port = self.reckon_port(response.content, port[0]) 
                    except Exception as msg:
                        continue

                    if port:
                        message = {
                                'ip': ip[0].strip(),
                                'port': int(port)
                                }
                        code = self.check_proxy_ip(ip[0].strip(), int(port))
                        if code == 200:
                            print message
                            self.save(json.dumps(message))

    def download_proxy_ru(self):
        url = 'http://proxy.com.ru/list_%s.html'
        for i in xrange(1,60):
            link = url%i
            try:
                response = requests.get(link, timeout=5)
                print time.strftime('%Y-%m-%d %H:%M:%S  ', time.localtime()), link
                if response.status_code == 200:
                    bs = BeautifulSoup(response.content)
                    table = bs.find_all(attrs={'style': re.compile('^TABLE-LAYOUT')})
                    for proxy in table[3].find_all('tr'):
                        tr = proxy.find_all('td')
                        try:
                            ip = tr[1].get_text()
                            port = tr[2].get_text()
                            text = tr[4].get_text()

                            if not ip or not port or \
                                (port and not port.isdigit()):
                                continue

                            if u'省' in text or \
                                    u'市' in text:
                                message = {
                                          'ip': ip.strip(),
                                          'port': int(port.strip())
                                }
                                code = self.check_proxy_ip(ip.strip(), port.strip())
                                if code == 200:
                                    self.save(json.dumps(message)) 
                        except Exception as msg:
                            continue

            except:
                continue

    def download_parse(self, url):
        req = requests.Session()
        proxies = {'http': 'http://111.161.126.100:80'} 
        header = {'Accept-Charset':'GBK,utf-8;q=0.7,*;q=0.3','User-Agent' : 'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US) AppleWebKit/534.16 (KHTML, like Gecko) Chrome/10.0.648.151 Safari/534.16'}
        
        response = req.get(url, proxies=proxies, timeout=10, headers=header)
        print response.status_code
        if response.status_code == 200:
            bs = BeautifulSoup(response.content)
            ips = bs.find_all('tr')
            for ip in ips:
                infos = ip.select('td')
                
                if not infos:
                    continue

                try:
                    ip = re.findall('\d+\.\d+\.\d+\.\d+', infos[0].string)
                    port = re.findall('\d+', infos[1].string)
                except:
                    continue

                if not ip or not port:
                    continue

                message = {
                        'ip': infos[0].string,
                        'port': int(infos[1].string)
                        }
                print message
                self.save(json.dumps(message))

    def update_vpn(self):
        total = self.redis.llen('vpn')

        if (total-self.count):
            for i in xrange(self.count):
                self.redis.lpop('vpn')
        else:
            log.msg('check update vpn-process', level=log.ERROR)
            

    def download_proxy_xici(self):
        links = ['http://www.xici.net.co/nt/1', \
                'http://www.xici.net.co/nn/1']
        header = {'Accept-Charset':'GBK,utf-8;q=0.7,*;q=0.3','User-Agent' : 'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US) AppleWebKit/534.16 (KHTML, like Gecko) Chrome/10.0.648.151 Safari/534.16'}

        for link in links:
            response = requests.get(link, headers=header)
            print response.status_code
            bs = BeautifulSoup(response.content)
            trs = bs.find_all('tr')
            for tr in trs:
                try:
                    tds = tr.find_all('td')
                    ip = tds[2].get_text()
                    port = tds[3].get_text()
                except Exception as msg:
                    print msg 
                    continue

                if not ip or not port or \
                    (port and not port.isdigit()):
                    continue

                message = { 
                        'ip': ip.strip(),
                        'port': int(port.strip())
                        }   
                print message
                code = self.check_proxy_ip(ip.strip(), port.strip())
                if code == 200:
                    self.save(json.dumps(message)) 

    def save(self, message):
        try:
            self.redis.rpush('vpn', message)
        except Exception as msg:
            print time.strftime('%Y-%m-%d %H:%M:%S  ', time.localtime()), msg

if __name__ == '__main__':
    main()

