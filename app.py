from flask import Flask, request, abort

from linebot import (
	LineBotApi, WebhookHandler
)
from linebot.exceptions import (
	InvalidSignatureError
)
from linebot.models import *

import re
import requests
from bs4 import BeautifulSoup
import multiprocessing as mp

app = Flask(__name__)

line_bot_api = LineBotApi('Your Channel access token ')
handler = WebhookHandler('YOUR_CHANNEL_SECRET')

find_flag = 0

@app.route("/callback", methods=['POST'])
def callback():
	signature = request.headers['X-Line-Signature']
	body = request.get_data(as_text=True)
	app.logger.info("Request body: " + body)
	try:
		handler.handle(body, signature)
	except InvalidSignatureError:
		abort(400)
	return 'OK'

def get_picture_job(url):
	html = requests.get(url)
	soup = BeautifulSoup(html.text, "lxml")
	pic = soup.select('.table img')
	return pic[0]['src']

def get_movie_for_pic():
	movie_url_list = []
	crawl_url = "https://movies.yahoo.com.tw/chart.html"
	html = requests.get(crawl_url)
	soup = BeautifulSoup(html.text, "lxml")
	search = soup.select('.tr a')
	for l in search:
		if "https://movies.yahoo.com.tw/movieinfo_main/" in l['href']:
			movie_url_list.append(l['href'])
	return movie_url_list

def check_movie_existance(name_list, user_input_name):
	for name in name_list:
		if user_input_name in name:
			location = name_list.index(name)
			found_flag = 1
			break
		else:
			found_flag = 0

	if found_flag == 1:
		return location
	else:
		return -1

def check_movie_timetable(crawl_url):
	count = 1
	content = ""
	base_url = "http://www.atmovies.com.tw"
	html = requests.get(crawl_url)
	soup = BeautifulSoup(html.text, "lxml")
	search = soup.select('.movie_theater option')
	if len(search) > 0:
		del search[0]
		for l in search:
			content += '{}. {}\n{}\n'.format(count, re.sub("[\r\n\t']", '', l.text.strip()),\
			 			base_url + l['value'])
			count += 1
	else:
		content += "此電影已經不再全臺的電影院播出了！\n\
		可以再重新找找別的電影喲！\n"
	return content

def get_movie_list():
	movie_name_list = []
	movie_url_list = []
	base_url = "http://app2.atmovies.com.tw"
	movie_list_url = "/boxoffice/twweekend/"
	crawl_url = base_url + movie_list_url
	html = requests.get(crawl_url)
	soup = BeautifulSoup(html.text, "lxml")
	search = soup.select('.at11 a')
	for l in search:
		movie_name_list.append(l.text)
		movie_url_list.append(base_url + l['href'])
	return movie_name_list, movie_url_list

def set_up_message(name_list, url_list):
	count = 1
	content = ""
	for l in range(len(name_list)):
		content += '{}. {}\n{}\n'.format(count,name_list[l], url_list[l])
		count += 1
	return content


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
	global find_flag
	content_msg = ''
	movie_names, movie_urls = get_movie_list()

	if event.message.text == "[服務]找電影":
		movie_names, movie_urls = get_movie_list()
		content_msg = set_up_message(movie_names, movie_urls)
		line_bot_api.push_message(event.source.user_id, TextSendMessage(text = content_msg))
		#line_bot_api.reply_message(event.reply_token, TextSendMessage(text = content_msg))

	elif event.message.text == "[服務]找時刻":
		msg = "你想看什麼電影呢？\n" +\
				"我可以幫你找電影院的時刻表哦！\n"+\
				"如果你想看 死侍 這部電影， 請輸入：\n"+\
				"死侍\n"+\
				"你也可以輸入找電影功能內對應電影名稱的數字：\n"+\
				"8"
		find_flag = 1
		line_bot_api.reply_message(
			event.reply_token,
			TextSendMessage(text = msg))

	elif event.message.text == "[服務]TOP 5 影片":
		movie_urls_pic = get_movie_for_pic()
		pool = mp.Pool(5)
		crawl_jobs = [pool.apply_async(get_picture_job, args=(url,)) for url in movie_urls_pic[0:5]]
		pictures = [j.get() for j in crawl_jobs]
		message = TemplateSendMessage(
			alt_text='ImageCarousel template',
			template=ImageCarouselTemplate(
				columns=[
					ImageCarouselColumn(
						image_url=pictures[0],
						action=URITemplateAction(
							label="查看",
							uri=movie_urls_pic[0]
						)
					),
					ImageCarouselColumn(
						image_url=pictures[1],
						action=URITemplateAction(
							label="查看",
							uri=movie_urls_pic[1]
						)
					),
					ImageCarouselColumn(
						image_url=pictures[2],
						action=URITemplateAction(
							label="查看",
							uri=movie_urls_pic[2]
						)
					),
					ImageCarouselColumn(
						image_url=pictures[3],
						action=URITemplateAction(
							label="查看",
							uri=movie_urls_pic[3]
						)
					),
					ImageCarouselColumn(
						image_url=pictures[4],
						action=URITemplateAction(
							label="查看",
							uri=movie_urls_pic[4]
						)
					)
				]
			)
		)

		line_bot_api.push_message(event.source.user_id, message)
		#line_bot_api.reply_message(event.reply_token,message)

	elif find_flag == 1:
		if event.message.text.isdigit():
			if ( int(event.message.text) > 20 or int(event.message.text) < 0 ):
				result = -1
			else:
				result = int(event.message.text) - 1
		else:
			result = check_movie_existance(movie_names, event.message.text)

		if result == -1:
			content_msg = "無法找到影片\n"+\
							"請重新點選功能選單內的找時刻\n"+\
							"再輸入正確電影名字 或 對應電影的數字\n"
			line_bot_api.push_message(event.source.user_id, TextSendMessage(text = content_msg))
		else:
			content_msg = check_movie_timetable(movie_urls[result])
			msg = "這是 {} 在不同地區的時刻表 : \n".format(movie_names[result]) +\
					content_msg
			line_bot_api.push_message(event.source.user_id, TextSendMessage(text = msg))
		find_flag = 0

	else :
		msg = "請重新輸入"
		line_bot_api.reply_message(
			event.reply_token,
			TextSendMessage(text = msg))

if __name__ == "__main__":
	app.run()
	#app.run(debug=True,port=)
