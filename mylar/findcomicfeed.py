#!/usr/bin/env python

import os
import sys
import time
import requests
import feedparser
import re
from . import logger
import mylar
import unicodedata
import urllib.request, urllib.parse, urllib.error

def Startit(searchName, searchIssue, searchYear, ComicVersion, IssDateFix, booktype=None):
    timerdelay = 5

    cName = searchName

    #clean up searchName due to webparse/redudant naming that would return too specific of results.
    commons = ['and', 'the', '&', '-']
    for x in commons:
        cnt = 0
        for m in re.finditer(x, searchName.lower()):
            cnt +=1
            tehstart = m.start()
            tehend = m.end()
            if any([x == 'the', x == 'and']):
                if len(searchName) == tehend:
                    tehend =-1
                if all([tehstart == 0, searchName[tehend] == ' ']) or all([tehstart != 0, searchName[tehstart-1] == ' ', searchName[tehend] == ' ']):
                    searchName = searchName.replace(x, ' ', cnt)
                else:
                    continue
            else:
                searchName = searchName.replace(x, ' ', cnt)

    searchName = re.sub('\s+', ' ', searchName)
    searchName = re.sub("[\,\:]", "", searchName).strip()
    searchName = re.sub("[\/]", " ", searchName).strip()
    splitSearch = searchName.split(" ")

    tmpsearchIssue = searchIssue

    if any([booktype == 'One-Shot', booktype == 'TPB']):
        tmpsearchIssue = '1'
        loop = 4
    elif len(searchIssue) == 1:
        loop = 3
    elif len(searchIssue) == 2:
        loop = 2
    else:
        loop = 1

    if "-" in searchName:
        searchName = searchName.replace("-", '((\\s)?[-:])?(\\s)?')
    regexName = searchName.replace(" ", '((\\s)?[-:])?(\\s)?')

    if mylar.CONFIG.USE_MINSIZE is True:
        minsize = mylar.CONFIG.MINSIZE
    else:
        minsize = 10

    if mylar.CONFIG.USE_MAXSIZE is True:
        maxsize = mylar.CONFIG.MAXSIZE
    else:
        maxsize = 0

    if mylar.CONFIG.USENET_RETENTION is not None:
        max_age = mylar.CONFIG.USENET_RETENTION
    else:
        max_age = 0
    feed = []
    i = 1
    searchline = ''
    issue_search = []

    while (i <= loop):
        if i == 1:
            searchmethod = tmpsearchIssue
        elif i == 2:
            searchmethod = '0' + tmpsearchIssue
        elif i == 3:
            searchmethod = '00' + tmpsearchIssue
        elif i == 4:
            searchmethod = tmpsearchIssue
        else:
            break

        if i == 4:
            joinSearch = " ".join(splitSearch)
        else:
            joinSearch = " ".join(splitSearch) + " " +searchmethod

        issue_search.append(searchmethod)

        if mylar.CONFIG.PREFERRED_QUALITY == 1: joinSearch = joinSearch + " .cbr"
        elif mylar.CONFIG.PREFERRED_QUALITY == 2: joinSearch = joinSearch + " .cbz"

        if i == 1:
           searchline += joinSearch  #'"' + joinSearch + '"'
        else:
           searchline += ' | ' + joinSearch  #' | "' + joinSearch + '"'

        i+=1

    params = {'q': searchline,
              'max': 50,
              'minage': 0,
              'maxage': max_age,
              'hidespam': 1,
              'hidepassword': 1,
              'sort': 'agedesc',
              'minsize': minsize,
              'maxsize': maxsize,
              'complete': 0,
              'hidecross': 0,
              'hasNFO': 0,
              'poster': "",
              'g[]': 85}

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.90 Safari/537.36'}

    logger.fdebug('[EXPERIMENTAL] Now searching experimental for %s with numeric issue variations of %s to try and ensure all the bases are covered' % (cName, issue_search))
    url_params = urllib.parse.urlencode(params)

    time.sleep(timerdelay)
    try:
        r = requests.get(mylar.EXPURL + 'search/rss', params=url_params, verify=True, headers=headers)
    except Exception as e:
        logger.warn('[EXPERIMENTAL][ERROR] %s' % e)
        return "no results"

    if r.status_code != 200:
        #typically 403 will not return results, but just catch anything other than a 200
        if r.status_code == 403:
            return "no results"
        else:
            logger.warn('[EXPERIMENTAL] Status code returned: %s' % (r.status_code))
            if r.status_code == 503:
                logger.warn('[EXPERIMENTAL] Site appears unresponsive/down. Disabling...')
                return 'disable'
            else:
                return "no results"
    else:
        logger.info('[EXPERIMENTAL] Now compiling results...')
        try:
            feed = feedparser.parse(r.content)
        except Exception as e:
            # if it fails to parse, it's either invalid schema or no results.
            return "no results"

    entries = []
    mres = {}
    totNum = len(feed.entries)
    keyPair = []
    regList = []
    countUp = 0

    while countUp < totNum:
        try:
            urlParse = feed.entries[countUp].enclosures[0]
            keyPair.append({
                "title":     feed.entries[countUp].title,
                "link":      urlParse["href"],
                "length":    urlParse["length"],
                "pubdate":   feed.entries[countUp].updated})

        except Exception as e:
            logger.warn('[EXPERIMENTAL] Experimental returned bad data. This might be due to being down or requesting too fast.')

        countUp = countUp + 1

    # thanks to SpammyHagar for spending the time in compiling these regEx's!

    regExTest=""

    regEx = "(%s\\s*(0)?(0)?%s\\s*\\(%s\\))" %(regexName, searchIssue, searchYear)
    regExOne = "(%s\\s*(0)?(0)?%s\\s*\\(.*?\\)\\s*\\(%s\\))" %(regexName, searchIssue, searchYear)

    #Sometimes comics aren't actually published the same year comicVine says - trying to adjust for these cases
    regExTwo = "(%s\\s*(0)?(0)?%s\\s*\\(%s\\))" %(regexName, searchIssue, int(searchYear) +1)
    regExThree = "(%s\\s*(0)?(0)?%s\\s*\\(%s\\))" %(regexName, searchIssue, int(searchYear) -1)
    regExFour = "(%s\\s*(0)?(0)?%s\\s*\\(.*?\\)\\s*\\(%s\\))" %(regexName, searchIssue, int(searchYear) +1)
    regExFive = "(%s\\s*(0)?(0)?%s\\s*\\(.*?\\)\\s*\\(%s\\))" %(regexName, searchIssue, int(searchYear) -1)

    regexList=[regEx, regExOne, regExTwo, regExThree, regExFour, regExFive]

    except_list=['releases', 'gold line', 'distribution', '0-day', '0 day', '0day', 'o-day']
    block_regex = r"\[\d{2,3}\/\d{2,3}\]"

    for entry in keyPair:
        title = entry['title']
        splitTitle = title.split("\"")
        noYear = 'False'
        _digits = re.compile('\d')
        subcnt = 0
        for subs in splitTitle:
            regExCount = 0
            if len(subs) >= len(cName) and not (any(d in subs.lower() for d in except_list) or re.search(block_regex, subs)) and bool(_digits.search(subs)) is True:
                # this will still match on crap like 'For SomeSomayes' especially if the series length < 'For SomeSomayes'
                if subs.lower().startswith('for'):
                    if cName.lower().startswith('for'):
                        pass
                    else:
                        #this is the crap we ignore. Continue (commented else, as it spams the logs)
                        #logger.fdebug('this starts with FOR : ' + str(subs) + '. This is not present in the series - ignoring.')
                        subcnt += 1
                        continue

                p = re.compile(r'\d{4}\-(0?[1-9]|1[012])\-(0?[1-9]|[12][0-9]|3[01])*')
                d = p.match(subs)
                if d:
                    dtchk = d.group()
                    if any(['2019' in dtchk, '2020' in dtchk, '2021' in dtchk]) and subcnt == 0:
                        subcnt += 1
                        continue

                #logger.fdebug('match.')
                if IssDateFix != "no":
                    if IssDateFix == "01" or IssDateFix == "02": ComicYearFix = str(int(searchYear) - 1)
                    else: ComicYearFix = str(int(searchYear) + 1)
                else:
                    ComicYearFix = searchYear

                if searchYear not in subs and ComicYearFix not in subs:
                    noYear = 'True'
                    noYearline = subs

                if (searchYear in subs or ComicYearFix in subs) and noYear == 'True':
                    #this would occur on the next check in the line, if year exists and
                    #the noYear check in the first check came back valid append it
                    subs = noYearline + ' (' + searchYear + ')'
                    noYear = 'False'

                if noYear == 'False':
                    entries.append({
                              'title':     subs,
                              'link':      entry['link'],
                              'pubdate':   entry['pubdate'],
                              'length':    entry['length']
                              })
                    break
            subcnt +=1

    if len(entries) >= 1:
        mres['entries'] = entries
        return mres
    else:
        logger.fdebug("No Results Found")
        return "no results"
