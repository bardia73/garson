# -*- coding: utf-8 -*-
from http.cookiejar import Cookie, urllib, CookieJar
import random
from bs4 import BeautifulSoup
import re
from bot.scraper import get_captcha
from configuration.models import Food
from userpanel.models import UserCollection
from selenium import webdriver
from pyvirtualdisplay import Display
import contextlib
from selenium.common.exceptions import NoSuchElementException

__author__ = 'bardia'


def _get_foods(contents):
    all_names = Food.get_all_name()

    food_chart = [[[], [], []] for i in range(6)]
    soup = BeautifulSoup(contents)
    day_trs = soup.find(id="pageTD").table.find_all('tr')[1].td.table.tbody.find_all('tr', recursive=False)[1:]
    for day_tr in day_trs:
        if str(day_tr).find(u"پنجشنبه") != -1:
            day = 5
        elif str(day_tr).find(u"چهارشنبه") != -1:
            day = 4
        elif str(day_tr).find(u"سه شنبه") != -1:
            day = 3
        elif str(day_tr).find(u"دوشنبه") != -1:
            day = 2
        elif str(day_tr).find(u"یکشنبه") != -1:
            day = 1
        elif str(day_tr).find(u"شنبه") != -1:
            day = 0
        else:
            print('error')
            continue
        foods_tds = day_tr.find_all('td', recursive=False)[1:]
        for time in range(3):
            foods_td = foods_tds[time]
            if foods_td.table is None:
                continue
            if 'checked="checked"' in str(foods_td):
                print('\t', day, time, "is checked")
                continue

            food_trs = foods_td.table.tbody.find_all('tr', recursive=False)
            for tr in food_trs:
                number = re.findall(r'id="userWeekReserves\.selected(\d+)"', str(tr))[0]
                str_for_name = tr.span.text
                name = str_for_name.split('|')[1].strip()
                food_chart[day][time].append((number, name))
                if name not in all_names:
                    with open("found_food.txt", "a") as my_file:
                        my_file.write(name + '\n')

    return food_chart


def choose_food(user, foods):
    random_choice = []

    list1 = [Food.get_name(i) for i in user.food_list_1]
    list2 = [Food.get_name(i) for i in user.food_list_2]

    for fav_food in list1:
        for food in foods:
            if food[1] == fav_food:
                return food
    for food in foods:
        if food[1] in list2:
            random_choice.append(food)

    if len(random_choice) > 0:
        return random.choice(random_choice)
    return None


class Registerer:
    food_chart = None

    def __init__(self, user):
        self.user = user

    def register(self):
        if not (any(self.user.breakfast) or any(self.user.lunch) or any(self.user.dinner)):
            print("\tNothing to reserve.")
            return None
        try:
            display = Display(visible=False, size=(1600, 1200))
            display.start()
            with contextlib.closing(webdriver.Firefox()) as browser:
                cj = CookieJar()
                opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
                opener.addheaders = [('User-agent', 'Mozilla/5.0')]
                authentication_url = "https://stu.iust.ac.ir/j_security_check"
                payload = {"j_username": self.user.stu_username,
                           "j_password": self.user.stu_password,
                           "captcha_input": get_captcha(cj),
                           "login": u"ورود", }
                data = urllib.parse.urlencode(payload)
                binary_data = data.encode('UTF-8')
                request = urllib.request.Request(authentication_url, binary_data)
                response = opener.open(request)
                cj.extract_cookies(response, request)
                print(cj._cookies)
                contents = str(response.read(), 'utf-8')

                if u'iconWarning.gif' in contents:
                    print("wrong user pass")
                    return "wup"

                new_cookie = {'expiry': None, 'value':cj._cookies['stu.iust.ac.ir']['/']['JSESSIONID'].value, 'name': 'JSESSIONID', 'secure': True, 'path': '/', 'domain': 'stu.iust.ac.ir'}

                #browser = webdriver.Firefox()
                browser.get("https://stu.iust.ac.ir")
                browser.add_cookie(new_cookie)

                # TODO: handle wrong user or pass
                browser.get("https://stu.iust.ac.ir/nurture/user/multi/reserve/showPanel.rose")
                browser.find_element_by_id("nextWeekBtn").click()
                import time

                for self_id in set(self.user.breakfast + self.user.lunch + self.user.dinner) - {0}:
                    # browser.get("https://stu.iust.ac.ir/nurture/user/multi/reserve/showPanel.rose")
                    self_hidden_id = None
                    for i in range(10):
                        try:
                            self_hidden_id = browser.find_element_by_id("selfHiddenId")
                            break
                        except:
                            time.sleep(0.3)

                    if self_hidden_id.get_attribute('value') != self_id:
                        try:
                            browser.find_element_by_id("selfId").find_element_by_xpath(
                                "//option[@value='" + str(self_id) + "']").click()
                        except NoSuchElementException:
                            print("\tERR - Invalid self: {} self:{}".format(self.user.stu_username, self_id))
                            continue
                    foods_to_register = []
                    food_chart = _get_foods(browser.page_source)

                    for i, day in enumerate(self.user.breakfast):
                        if day == self_id:
                            foods_in_day = food_chart[i][0]
                            chosen = choose_food(self.user, foods_in_day)
                            if chosen is not None:
                                foods_to_register.append(chosen)
                    for i, day in enumerate(self.user.lunch):
                        if day == self_id:
                            foods_in_day = food_chart[i][1]
                            chosen = choose_food(self.user, foods_in_day)
                            if chosen is not None:
                                foods_to_register.append(chosen)
                    for i, day in enumerate(self.user.dinner):
                        if day == self_id:
                            foods_in_day = food_chart[i][2]
                            chosen = choose_food(self.user, foods_in_day)
                            if chosen is not None:
                                foods_to_register.append(chosen)

                    for index, food_to_check in foods_to_register:
                        print("\t->" + str(food_to_check))
                        browser.find_element_by_id("userWeekReserves.selected" + str(index)).click()
                    browser.find_element_by_id("doReservBtn").click()

        except Exception as e:
            return str(e)
            # browser.quit()
        display.stop()
        return None


if __name__ == "__main__":
    # user = UserCollection.objects(stu_username="92522267", stu_password="**")[0]
    user = UserCollection.objects(stu_username="92521114", stu_password="***")[0]
    reg = Registerer(user)
    reg.register()
    # # print(choose_food(user, [('6', 'رشته پلو'), ('7', 'زرشك پلو با مرغ')]))
