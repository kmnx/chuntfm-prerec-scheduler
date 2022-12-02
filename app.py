from flask import Flask, request, render_template, redirect, url_for
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from datetime import datetime, timedelta
import subprocess
import logging
import configparser


jobstores = {
    'default': SQLAlchemyJobStore(url='sqlite:///jobs.sqlite')
}

#
# parse config

config = configparser.ConfigParser()
config.read('config.ini')


app = Flask(__name__)

app.config['title'] = config['DEFAULT']['title']

# initialize scheduler with your preferred timezone
scheduler = BackgroundScheduler({'apscheduler.timezone': 'Europe/London'}, jobstores=jobstores)
scheduler.start()

logging.basicConfig(filename='scheduler.log', level=logging.INFO)

@app.route('/', methods = ['GET'])
def index():
    return render_template('index.html')


@app.route('/add', methods=['GET', 'POST'])
def add_prerec_play(setup_time = 15):

    try:

        if request.method == 'GET':

            #@TODO show form to add prerecs

            return render_template('add_prerec.html')

        elif request.method == 'POST':

            form_post = False

            if request.args.get('form') is not None:

                form_post = True

                # get the form data
                data = request.form

                data = data.to_dict()

            else:

                data = request.get_json()

            if 'name' not in data:
                return 'name not in data'
            else:
                job_name = data['name']

            if 'file_path' not in data:
                return 'file_path not supplied'
            else:
                file_path = data['file_path']

            #
            if 'start_time' not in data:
                return 'start_time not supplied'
            else:
                start_time = data['start_time']

            if 'stop_time' in data:
                stop_time = data['stop_time']
            else:
                stop_time = None

            #convert to datetime

            start_date_time = datetime.strptime(start_time, '%Y-%m-%dT%H:%M')

            # add setup time to start time
            start_date_time = start_date_time - timedelta(seconds=int(config['DEFAULT']['liq_setup_time']))

            if stop_time is not None and stop_time != '':
                stop_date_time = datetime.strptime(stop_time, '%Y-%m-%dT%H:%M')
                stop_seconds = (stop_date_time - start_date_time).total_seconds()

                if stop_date_time < start_date_time:
                    raise Exception('Stop time must be after start time')

            else:
                stop_seconds = None


            # add start job to scheduler
            scheduler.add_job(stream_file, 'date', name=job_name, run_date=start_date_time, args=[file_path, stop_seconds])

            if form_post:
                return render_template('add_prerec.html', success=True, job_name=job_name)
            else:
                return "Pre-recorded play added to scheduler"

    except Exception as e:

        if form_post:
            return render_template('add_prerec.html', error=True, error_message=e)
        else:
            return str(e)



# delete a job given <id>
@app.route('/delete/<id>', methods=['GET', 'DELETE'])
def delete_prerec_play_by_id(id):
    try:
        scheduler.remove_job(id)

        if request.method == 'GET':
            return redirect(url_for('.list_sheduled_prerecs', _external=True, page=True, delete_success=True, job_name=id))
        else:
            return "Pre-recorded play deleted from scheduler"
    except Exception as e:
        if request.method == 'GET':
            return redirect(url_for('.list_sheduled_prerecs', _external=True, page=True, delete_error=True, job_name=id))
        else:
            return str(e)

@app.route('/list', methods=['GET'])
def list_sheduled_prerecs():

    # get args dict
    args = request.args.to_dict()


    jobs = []

    for job in scheduler.get_jobs():
        jobs.append({
            'id': job.id,
            'name': job.name,
            'next_run_time': job.next_run_time,
            'args': job.args,
            'kwargs': job.kwargs
        })

    if args.get('page') is not None:
        return render_template('list_prerecs.html', jobs=jobs, **args)
    else:
        return jobs



def stream_file(file_path, stop_after = None):

    # write prerec file path to prerec.m3u
    with open('prerec.m3u', 'w') as f:
        f.write(file_path)

    # stream the audio file using a subsprocess and liquidsoap
    subprocess.check_output(['liquidsoap', 'prerec.liq'], timeout=stop_after)


if __name__ == '__main__':
    app.run()
