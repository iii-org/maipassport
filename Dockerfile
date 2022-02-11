FROM dockerbase

ENV PYTHONUNBUFFERED 1
ENV DJANGO_SETTINGS_MODULE config.settings.mimic-production

RUN mkdir /maipassport

WORKDIR /maipassport

#COPY requirements/local.txt ./requirements/local.txt

#RUN apt-get update && \
#    apt-get install -y gettext
#
#RUN apt-get install -y libzbar0 libgl1-mesa-glx
#
#RUN pip install -r requirements/local.txt

COPY . .

#CMD python manage.py collectstatic --no-input \
#    && gunicorn --workers=2 config.wsgi -b 0.0.0.0:8000 --reload --error-logfile '/maipassport/log/gunicorn-error.log'

CMD python manage.py collectstatic --no-input \
    && gunicorn --workers=2 config.wsgi -b 0.0.0.0:8000 --reload --error-logfile '/maipassport/log/gunicorn-error.log'

#CMD ./dist/manage/manage runserver