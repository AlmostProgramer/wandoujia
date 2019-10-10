import scrapy
import re
import json
from urllib.parse import urlencode
from wandoujia.items import WandoujiaItem


class wandoujiaSpider(scrapy.Spider):
    name = 'wandoujia'

    def __init__(self):
        #豌豆荚软件分类页面，用来获取软件类别
        self.cate_url = 'https://www.wandoujia.com/category/app'
        #基础url，通过获取到的软件类别code来补充完整url
        self.base_url = 'https://www.wandoujia.com/category/'
        #ajax页面url，也需要通过配置参数来完整url
        self.ajax_url = 'https://www.wandoujia.com/wdjweb/api/category/more?'
        #创建一个豌豆荚软件类别类来包装一些程序
        self.wandou_category = Get_category()

    #第一步访问豌豆荚软件分类页面，获取软件类别信息
    def start_requests(self):
        yield scrapy.Request(self.cate_url,callback=self.get_category)

    #第二步，解析软件类别信息，通过基础url来访问相应目录下的软件页面（第一页）
    def get_category(self,response):
        #类别字典列表，含有三条信息（主类别名称，主类别code，子类别信息的字典）
        cate_content = self.wandou_category.parse_category(response)
##        print(cate_content[:5])
        #遍历主类别
        for item in cate_content:
            cate_name = item['cate_name']#主类别名称
            cate_code = item['cate_code']#主类别code
            for cate_child in item['cate_children']:#遍历子类别，提取相应的名称与code
                cate_child_name = cate_child['cate_child_name']
                cate_child_code = cate_child['cate_child_code']
                #组建基础url
                url = self.base_url+str(cate_code)+'_'+str(cate_child_code)
##                print(url)
                #将相应信息也传到下一个解析函数parssse中
                dict = {'page':1,'cate_name':cate_name,'cate_code':cate_code,
                        'cate_child_name':cate_child_name,
                        'cate_child_code':cate_child_code}
                yield scrapy.Request(url,callback=self.parse,meta=dict)

    #解析第一页的信息并提取，同时递归访问其余Ajax页面（第二页及以后）
    def parse(self, response):
        #判断是否访问成功
        if len(response.body) >= 100:
            #这些信息是用来构建Ajax页面url的，也就是下一页的url
            page = response.meta['page']
            cate_name = response.meta['cate_name']
            cate_code = response.meta['cate_code']
            cate_child_name = response.meta['cate_child_name']
            cate_child_code = response.meta['cate_child_code']
            #判断是否为第一页，是第一页就可以直接解析页面了
            if page == 1:
                contents = response
            #不是第一页，还需要进入Ajax页面去取得HTML文档，在json['data']['content']下
            else:
                jsonresponse = json.loads(response.body_as_unicode())
                contents = jsonresponse['data']['content']
                #将其转化为scrapy的selector格式便于解析
                contents = scrapy.Selector(text=contents,type='html')
            ###解析网页提取信息开始###
            contents = contents.css('.card')
            for content in contents:
                item = WandoujiaItem()
                item['cate_name'] = self.clean_name(cate_name)
                item['cate_child_name'] = cate_child_name
                item['app_name'] = content.css('.name::text').extract_first()
                item['install'] = content.css('.install-count::text').extract_first()
                item['volume'] = content.css('.meta span:last-child::text').extract_first()
                item['comment'] = content.css('.comment::text').extract_first()
                item['icon_url'] = self.get_icon_url(content,page)
                yield item
            ####解析网页提取信息结束###

            print('本页面共爬去了{}个app!'.format(len(contents)))
            #页面标识
            page += 1
            #将参数组合成字典
            params = {
                'catId':cate_code,
                'subCatId':cate_child_code,
                'page':page
            }
            #构建Ajax页面的url
            url = self.ajax_url+urlencode(params)
##            print(url)
            #构建参数字典，返回给下一个parse函数使用
            dict = {'page': page, 'cate_name': cate_name, 'cate_code': cate_code,
                    'cate_child_name': cate_child_name,
                    'cate_child_code': cate_child_code}
            #递归
            yield scrapy.Request(url,callback=self.parse,meta=dict)

    #名称清除方法1 去除不能用于文件命名的特殊字符
    def clean_name(self, name):
        rule = re.compile(r"[\/\\\:\*\?\"\<\>\|]")  # '/ \ : * ? " < > |')
        name = re.sub(rule, '', name)
        return name

    #封装下载链接信息提取函数，便于书写解析函数代码
    def get_icon_url(self,item,page):
        if page == 1:
            if item.css('.icon::attr("src")').extract_first().startswith("https"):
                icon_url = item.css('.icon::attr("src")').extract_first()
            else:
                icon_url = item.css('.icon::attr("data-original")').extract_first()
        else:
            icon_url = item.css('.icon::attr("data-original")').extract_first()
        return icon_url





#对软件类别进行封装
class Get_category():
    #解析页面，获取主类别名称，主类别code，子类别（内容是名字与code的字典）
    def parse_category(self,response):
        category = response.css('li.parent-cate')
        data = [{
            'cate_name':cate.css('a.cate-link::text').extract_first(),
            'cate_code':self.get_category_code(cate),
            'cate_children':self.get_category_children(cate)
        } for cate in category]
        return data
    
    #获取主类别的code
    def get_category_code(self,item):
        cat_url = item.css('a.cate-link::attr("href")').extract_first()
        pattern = re.compile(r'.*/(\d+)')
        cate_code = re.search(pattern,cat_url)
        return cate_code.group(1)
    
    #获取主类别下子类别的名字与code
    def get_category_children(self,item):
        pattern = re.compile(r'.*_(\d+)')
        cat_children = item.css('div.child-cate a')
        data = [{
            'cate_child_name':child.css('::text').extract_first(),
            'cate_child_code':re.search(pattern,child.css('::attr("href")').extract_first()).group(1)
        } for child in cat_children]
        return data

