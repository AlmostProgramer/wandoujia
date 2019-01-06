import scrapy
import re
import json
from urllib.parse import urlencode
from wandoujia.items import WandoujiaItem


class wandoujiaSpider(scrapy.Spider):
    name = 'wandoujia'

    def __init__(self):
        self.cate_url = 'https://www.wandoujia.com/category/app'
        self.base_url = 'https://www.wandoujia.com/category/'
        self.ajax_url = 'https://www.wandoujia.com/wdjweb/api/category/more?'
        self.wandou_category = Get_category()

    def start_requests(self):
        yield scrapy.Request(self.cate_url,callback=self.get_category)

    def get_category(self,response):
        #类别字典列表
        cate_content = self.wandou_category.parse_category(response)
        print(cate_content[:5])
        for item in cate_content:
            cate_name = item['cate_name']
            cate_code = item['cate_code']
            for cate_child in item['cate_children']:
                cate_child_name = cate_child['cate_child_name']
                cate_child_code = cate_child['cate_child_code']

                url = self.base_url+str(cate_code)+'_'+str(cate_child_code)
                print(url)
                dict = {'page':1,'cate_name':cate_name,'cate_code':cate_code,
                        'cate_child_name':cate_child_name,
                        'cate_child_code':cate_child_code}
                yield scrapy.Request(url,callback=self.parse,meta=dict)

    def parse(self, response):

        if len(response.body) >= 100:
            page = response.meta['page']
            cate_name = response.meta['cate_name']
            cate_code = response.meta['cate_code']
            cate_child_name = response.meta['cate_child_name']
            cate_child_code = response.meta['cate_child_code']

            if page == 1:
                contents = response
            else:
                jsonresponse = json.loads(response.body_as_unicode())
                contents = jsonresponse['data']['content']
                contents = scrapy.Selector(text=contents,type='html')

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
            print('本页面共爬去了{}个app!'.format(len(contents)))
            page += 1
            params = {
                'catId':cate_code,
                'subCatId':cate_child_code,
                'page':page
            }
            url = self.ajax_url+urlencode(params)
            print(url)
            dict = {'page': page, 'cate_name': cate_name, 'cate_code': cate_code,
                    'cate_child_name': cate_child_name,
                    'cate_child_code': cate_child_code}
            yield scrapy.Request(url,callback=self.parse,meta=dict)

        # 名称清除方法1 去除不能用于文件命名的特殊字符
    def clean_name(self, name):
        rule = re.compile(r"[\/\\\:\*\?\"\<\>\|]")  # '/ \ : * ? " < > |')
        name = re.sub(rule, '', name)
        return name

    def get_icon_url(self,item,page):
        if page == 1:
            if item.css('.icon::attr("src")').extract_first().startswith("https"):
                icon_url = item.css('.icon::attr("src")').extract_first()
            else:
                icon_url = item.css('.icon::attr("data-original")').extract_first()
        else:
            icon_url = item.css('.icon::attr("data-original")').extract_first()
        return icon_url

class Get_category():
    def parse_category(self,response):
        category = response.css('li.parent-cate')
        data = [{
            'cate_name':cate.css('a.cate-link::text').extract_first(),
            'cate_code':self.get_category_code(cate),
            'cate_children':self.get_category_children(cate)
        } for cate in category]
        return data

    def get_category_code(self,item):
        cat_url = item.css('a.cate-link::attr("href")').extract_first()
        pattern = re.compile(r'.*/(\d+)')
        cate_code = re.search(pattern,cat_url)
        return cate_code.group(1)

    def get_category_children(self,item):
        pattern = re.compile(r'.*_(\d+)')
        cat_children = item.css('div.child-cate a')
        data = [{
            'cate_child_name':child.css('::text').extract_first(),
            'cate_child_code':re.search(pattern,child.css('::attr("href")').extract_first()).group(1)
        } for child in cat_children]
        return data

