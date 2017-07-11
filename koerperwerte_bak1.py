#!/usr/bin/env python

import os
import urllib
import json
import dateutil.parser

from google.appengine.api import users
from google.appengine.ext import ndb

from datetime import timedelta, date

import jinja2
import webapp2

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

DEFAULT_GROUP_NAME = 'public_koerperwerte_group'

def daterange(start_date, end_date):
    for n in range(int ((end_date - start_date).days)):
        yield start_date + timedelta(n)

def format_weight(weight):
    if weight == 0:
        return '00,0'
    else:
        return ('0' if weight < 10 else '') + str(weight / 10.0).replace('.', ',')

# We set a parent key on the 'Weighings' to ensure that they are all
# in the same entity group. Queries across the single entity group
# will be consistent. However, the write rate should be limited to
# ~1/second.

def koerperwerte_key(group_name=DEFAULT_GROUP_NAME):
    """Constructs a Datastore key for a Koerperwerte entity.

    We use group_name as the key.
    """
    return ndb.Key('Koerperwerte', group_name)


class Author(ndb.Model):
    """Sub model for representing an author."""
    identity = ndb.StringProperty(indexed=False)
    email = ndb.StringProperty(indexed=False)


class Weighing(ndb.Model):
    """A main model for representing an individual Koerperwerte entry."""
    author = ndb.StructuredProperty(Author)
    date = ndb.DateProperty(indexed=True)
    weight = ndb.IntegerProperty(indexed=False)
    created = ndb.DateTimeProperty(auto_now_add=True)

class Day:
    def __init__(self, date = date.today(), dirk = 0, gergan = 0, michael = 0, tristan = 0):
        self.date = date
        self.dirk = dirk
        self.gergan = gergan
        self.michael = michael
        self.tristan = tristan
    
    def __str__(self):
        return "Day(" + str(self.date) + ", dirk=" + str(self.dirk) + ", gergan=" + str(self.gergan) + ", michael=" + str(self.michael) + ", tristan=" + str(self.tristan) + ")"

class MainPage(webapp2.RequestHandler):

    def get(self):
        print self
        print users

        print 'user:'
        print users.get_current_user()
        print 'nickname:' + users.get_current_user().nickname()
        
        group_name = self.request.get('group_name', DEFAULT_GROUP_NAME)
        weighings_query = Weighing.query(ancestor=koerperwerte_key(group_name)).order(Weighing.date)
        single_weighings = weighings_query.fetch(100)
        
        if len(single_weighings) == 0:
            dirk = Author(identity='dirk', email='dirk@podolak.de')
            gergan = Author(identity='gergan', email='gergan@penkov.de')
            michael = Author(identity='michael', email='michael@bieber.de')
            tristan = Author(identity='tristan', email='tristan@baumbusch.de')
            
            weighing = Weighing(parent=koerperwerte_key(group_name))
            weighing.author = dirk
            weighing.date = date(2017, 5, 1)
            weighing.weight = 845
            weighing.put()
            
            weighing = Weighing(parent=koerperwerte_key(group_name))
            weighing.author = gergan
            weighing.date = date(2017, 5, 1)
            weighing.weight = 825
            weighing.put()
            
            weighing = Weighing(parent=koerperwerte_key(group_name))
            weighing.author = michael
            weighing.date = date(2017, 5, 1)
            weighing.weight = 755
            weighing.put()
            
            weighing = Weighing(parent=koerperwerte_key(group_name))
            weighing.author = tristan
            weighing.date = date(2017, 5, 1)
            weighing.weight = 825
            weighing.put()
            
            weighing = Weighing(parent=koerperwerte_key(group_name))
            weighing.author = dirk
            weighing.date = date(2017, 5, 2)
            weighing.weight = 841
            weighing.put()
            
            weighing = Weighing(parent=koerperwerte_key(group_name))
            weighing.author = gergan
            weighing.date = date(2017, 5, 2)
            weighing.weight = 824
            weighing.put()
            
            weighing = Weighing(parent=koerperwerte_key(group_name))
            weighing.author = michael
            weighing.date = date(2017, 5, 2)
            weighing.weight = 756
            weighing.put()
            
            weighing = Weighing(parent=koerperwerte_key(group_name))
            weighing.author = tristan
            weighing.date = date(2017, 5, 2)
            weighing.weight = 823
            weighing.put()
            
            weighing = Weighing(parent=koerperwerte_key(group_name))
            weighing.author = dirk
            weighing.date = date(2017, 5, 8)
            weighing.weight = 821
            weighing.put()
            
            weighing = Weighing(parent=koerperwerte_key(group_name))
            weighing.author = tristan
            weighing.date = date(2017, 5, 8)
            weighing.weight = 820
            weighing.put()
            
            weighings_query = Weighing.query(ancestor=koerperwerte_key(group_name)).order(-Weighing.date)
            single_weighings = weighings_query.fetch(100)
            
        dates = set()
        days_dict = {}
        for single_weighing in single_weighings:
            weighing_date = single_weighing.date
            day = days_dict.get(weighing_date, Day(date = weighing_date))
            setattr(day, single_weighing.author.identity, single_weighing.weight)
            days_dict[weighing_date] = day
            dates.add(weighing_date)
        
        days = []
        start_date = min(dates)
        end_date = max(dates) + timedelta(days = 1)
        date_range = daterange(start_date, end_date)
        for single_date in date_range:
            if single_date in dates:
                days.append(days_dict[single_date])
            else:
                days.append(Day(date = single_date))

        user = users.get_current_user()
        if user:
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'

        template_values = {
            'user': user,
            'days': reversed(days),
            'group_name': urllib.quote_plus(group_name),
            'url': url,
            'url_linktext': url_linktext,
        }

        template = JINJA_ENVIRONMENT.get_template('index2.html')
        self.response.write(template.render(template_values))

class Sign(webapp2.RequestHandler):

    def post(self):
        # We set the same parent key on the 'Weighing' to ensure each
        # Weighing is in the same entity group. Queries across the
        # single entity group will be consistent. However, the write
        # rate to a single entity group should be limited to
        # ~1/second.
        group_name = self.request.get('group_name', DEFAULT_GROUP_NAME)
        weighing = Weighing(parent=koerperwerte_key(group_name))

        if users.get_current_user():
            greeting.author = Author(
                    identity=users.get_current_user().user_id(),
                    email=users.get_current_user().email())

        weighing.date = self.request.get('date')
        weighing.weight = self.request.get('weight')
        weighing.put()

        query_params = {'group_name': group_name}
        self.redirect('/?' + urllib.urlencode(query_params))

class Koerperwerte(webapp2.RequestHandler):

    def post(self):
        weight_request = json.loads(self.request.body)
        
        group_name = self.request.get('group_name', DEFAULT_GROUP_NAME)
        weighing = Weighing(parent=koerperwerte_key(group_name))
        weighing.author = Author(identity = users.get_current_user().user_id(), email = users.get_current_user().email())
        weighing.date = dateutil.parser.parse(weight_request['date'])
        weighing.weight = int(weight_request['weight'].replace(',', ''))
        
        if users.get_current_user():
            group_name = self.request.get('group_name', DEFAULT_GROUP_NAME)
            weighing = Weighing(parent=koerperwerte_key(group_name))
            weighing.author = Author(identity = users.get_current_user().user_id(), email = users.get_current_user().email())
            weighing.date = dateutil.parser.parse(weight_request['date'])
            weighing.weight = int(weight_request['weight'].replace(',', ''))
            weighing.put()
        


        #weighing.date = self.request.get('date')
        #weighing.weight = self.request.get('weight')
        #weighing.put()

        #query_params = {'group_name': group_name}
        #self.redirect('/?' + urllib.urlencode(query_params))

JINJA_ENVIRONMENT.filters['format_weight'] = format_weight

app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/sign', Sign),
    ('/weighing', Koerperwerte),
], debug=True)
