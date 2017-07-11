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
        return '0,0'
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


class Person(ndb.Model):
    identity = ndb.StringProperty(indexed=False)
    email = ndb.StringProperty(indexed=False)


class Weighing(ndb.Model):
    person = ndb.StructuredProperty(Person)
    datum = ndb.DateProperty(indexed=True)
    weight = ndb.IntegerProperty(indexed=False)
    created = ndb.DateTimeProperty(auto_now_add=True)

class Day:
    def __init__(self, datum = date.today()):
        self.datum = datum
        self.entries = {}
    
    def __str__(self):
        user_string = ''
        
        for identity,value in self.entries.iteritems():
            user_string = user_string + identity + ' (' + str(value) + ') '
        
        return 'Day(' + str(self.datum) + ', ' + user_string + ')'
    
    def add_entry(self, identity, weight):
        self.entries[identity] = weight

class MainPage(webapp2.RequestHandler):

    def get(self):
        user = users.get_current_user()
        
        if user:
            template_values = self.template_values_with_user(user)
        else:
            template_values = {
                'group_name': urllib.quote_plus(self.request.get('group_name', DEFAULT_GROUP_NAME)),
                'url': users.create_login_url(self.request.uri),
                'url_linktext': 'Login',
            }

        template = JINJA_ENVIRONMENT.get_template('index.html')
        self.response.write(template.render(template_values))
    
    def template_values_with_user(self, user):
        group_name = self.request.get('group_name', DEFAULT_GROUP_NAME)
        parent_key = koerperwerte_key(group_name)
        
        single_weighings = self.get_weighings(parent_key, user)
        persons, person_identities = self.get_persons(single_weighings, user, parent_key)
        dates, days_dict = self.get_dates(single_weighings)
        days = reversed(self.normalize_days(days_dict, person_identities, dates))
                
        url = users.create_logout_url(self.request.uri)
        url_linktext = 'Logout'

        template_values = {
            'persons': persons,
            'user': user,
            'days': days,
            'group_name': urllib.quote_plus(group_name),
            'url': url,
            'url_linktext': url_linktext,
        }

        return template_values
    
    def get_weighings(self, parent_key, user):
        weighings_query = Weighing.query(ancestor=parent_key).order(Weighing.datum)
        weighings = weighings_query.fetch()

        if len(weighings) == 0:
            if user:
                weighing = Weighing(parent=parent_key)
                weighing.datum = date.today()
                weighing.weight = 0
                weighing.person = Person(identity = user.user_id(), email = user.email())
                weighing.put()
                weighings.append(weighing)
        
        return weighings
    
    def get_persons(self, single_weighings, user, parent_key):
        persons = set()
        person_identities = []
        current_user_found = False
        for single_weighing in single_weighings:
            persons.add(single_weighing.person.email)
            person_identities.append(single_weighing.person.identity)
            if user.user_id() == single_weighing.person.identity:
                current_user_found = True
        if not current_user_found:
            persons.add(user.email())
            person_identities.append(user.user_id())
            weighing = Weighing(parent=parent_key)
            weighing.datum = date.today()
            weighing.weight = 0
            weighing.person = Person(identity = user.user_id(), email = user.email())
            single_weighings.append(weighing)
        return persons,person_identities
    
    def get_dates(self, single_weighings):
        dates = set()
        days_dict = {}
        for single_weighing in single_weighings:
            weighing_date = single_weighing.datum
            day = days_dict.get(weighing_date, Day(datum = weighing_date))
            day.add_entry(single_weighing.person.identity, single_weighing.weight)
            days_dict[weighing_date] = day
            dates.add(weighing_date)
        return dates, days_dict
    
    def normalize_days(self, days_dict, person_identities, dates):
        days = []
        start_date = min(dates)
        end_date = max(dates) + timedelta(days = 1)
        date_range = daterange(start_date, end_date)
        
        for single_date in date_range:
            if single_date not in dates:
                days_dict[single_date] = Day(datum = single_date)
            days.append(days_dict[single_date])
        
        for days_date in days_dict:
            day = days_dict[days_date]
            days_persons = []
            for entry in day.entries:
                days_persons.append(entry)
            for identity in person_identities:
                if identity not in days_persons:
                    day.add_entry(identity, 0)
        return days

class Koerperwerte(webapp2.RequestHandler):

    def post(self):
        weight_request = json.loads(self.request.body)
        datum = dateutil.parser.parse(weight_request['datum'])
        
        user = users.get_current_user()
        
        if user:
            group_name = self.request.get('group_name', DEFAULT_GROUP_NAME)
            weighings_query = Weighing.query().filter(Weighing.datum == datum)
            single_weighings = weighings_query.fetch()
            new_data = True
            for single_weighing in single_weighings:
                if single_weighing.person.identity == user.user_id():
                    single_weighing.weight = int(weight_request['weight'].replace(',', ''))
                    single_weighing.put()
                    new_data = False
                    break
            
            if new_data:
                weighing = Weighing(parent=koerperwerte_key(group_name))
                weighing.person = Person(identity = user.user_id(), email = user.email())
                weighing.datum = dateutil.parser.parse(weight_request['datum'])
                weighing.weight = int(weight_request['weight'].replace(',', ''))
                weighing.put()

JINJA_ENVIRONMENT.filters['format_weight'] = format_weight

app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/weighing', Koerperwerte),
], debug=True)
