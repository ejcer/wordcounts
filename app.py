from flask import Flask, render_template, request
from flask.ext.sqlalchemy import SQLAlchemy
from flask import jsonify
import os
import requests

import operator
from stop_words import stop_words
from collections import Counter
from bs4 import BeautifulSoup
import re
import nltk

from rq import Queue
from rq.job import Job
from worker import conn



### Configuration ###

app = Flask(__name__)
app.config.from_object(os.environ['APP_SETTINGS'])
db = SQLAlchemy(app)

q = Queue(connection=conn)

#print(os.environ['APP_SETTINGS'])
#print(os.environ['DATABASE_URL'])


from models import *

### Routes ###

@app.route('/', methods=['GET', 'POST'])
def index():

	results = {}

	if request.method == "POST":
		#get url that they entered
		try:
			url = request.form['url']

			job = q.enqueue_call(
				func=count_and_save_words, args=(url,), result_ttl=5000
			)
			print(job.get_id())
		except:
			errors.append(
				"unable to get URL for main route."
			)
	return render_template('index.html', results=results)

@app.route("/results/<job_key>", methods=['GET'])
def get_results(job_key):

	job = Job.fetch(job_key, connection=conn)

	if job.is_finished:
		result = Result.query.filter_by(id=job.result).first()
		results = sorted(
			result.result_no_stop_words.items(),
			key=operator.itemgetter(1),
			reverse=True
		)[:10]
		return jsonify(results)
	else:
		return "NAY!", 202


### Helpers ###

def count_and_save_words(url):

    errors = []

    try:
        r = requests.get(url)
    except:
        errors.append(
            "Unable to get URL for count and save words, please try again"
        )
        return {"error": errors}

    # text processing
    raw = BeautifulSoup(r.text).get_text()
    nltk.data.path.append('./nltk_data/')  # set the path
    tokens = nltk.word_tokenize(raw)
    text = nltk.Text(tokens)

    # remove punctuation, count raw words
    nonPunct = re.compile('.*[A-Za-z].*')
    raw_words = [w for w in text if nonPunct.match(w)]
    raw_word_count = Counter(raw_words)

    # stop words
    no_stop_words = [w for w in raw_words if w.lower() not in stop_words]
    no_stop_words_count = Counter(no_stop_words)

    # save the results
    try:
        result = Result(
            url=url,
            result_all=raw_word_count,
            result_no_stop_words=no_stop_words_count
        )
        db.session.add(result)
        db.session.commit()
        return result.id
    except:
        errors.append("Unable to add item to database.")
        return {"error": errors}




if __name__ == '__main__':
	app.run()
