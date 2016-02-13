from ..util import to_uuid
from ..core.db import db
from ..core.model import User, ApplicationStatus, ApplicationSettings
from ..core.security import update_user
from ..core.applications import APPLICATION_HOME, get_application, get_application_list, get_application_settings, update_application_settings
from ..core.docker import get_client, create_application, delete_application, get_application_domain, get_application_status
from .. import app
from .form import ApplicationForm, ApplicationSettingsForm, ProfileForm

from flask import redirect, render_template, request, url_for, flash, abort, send_file, send_from_directory, jsonify
from flask_security.core import current_user
from flask_security.decorators import login_required
import time


@app.context_processor
def utility_processor():
    return dict(current_user=current_user, tracking_url=app.config.get("TRACKING_URL"), 
        version=app.config.get("VERSION"), ApplicationStatus=ApplicationStatus)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html', applications=get_application_list())

@app.route('/about.html', methods=['GET'])
def about():
    return render_template('about.html')

@app.route('/profile.html', methods=['GET'])
@login_required
def my_profile():
    return redirect(url_for('profile', login=current_user.login))

@app.route('/profile/<login>.html', methods=['GET', 'POST'])
@login_required
def profile(login):
    if current_user.login != login:
        abort(403, "You are not allowed to view this profile") 
    
    user = current_user
    
    form = ProfileForm(obj=user)
    if form.validate_on_submit():
        user.name = form.name.data
        update_user(user)
        return redirect(url_for('profile', login=login))

    return render_template('profile.html', user=current_user, form=form)

@app.route('/application/<application_id>.html', methods=['GET', 'POST'])
def application(application_id):
    application_status = None
    application_domain = None
    form = None

    if current_user.is_authenticated():
        application = get_application(application_id)
        client = get_client()

        form = ApplicationForm()
        
        if form.validate_on_submit():
            if form.start.data:
                create_application(client, current_user, application)
            
            if form.stop.data:
                delete_application(client, current_user, application)
            return redirect(url_for('application', application_id=application_id))
        
        application_status = get_application_status(client, current_user, application)
        application_domain = get_application_domain(current_user, application)

    return render_template('application.html', application=get_application(application_id), 
        application_status=application_status, application_domain=application_domain, form=form)

@app.route('/application/<application_id>.json', methods=['GET'])
@login_required
def application_status(application_id):
    client = get_client()
    application = get_application(application_id)
    client = get_client()
    status = get_application_status(client, current_user, application).name
    return jsonify(status=status)

@app.route('/static/applications/<path:path>')
def application_static(path):
    if not path[-3:] in ("png", "jpg"):
        raise Exception("Unsupported file")
    return send_from_directory(APPLICATION_HOME, path)

@app.route('/application/<application_id>/settings.html', methods=['GET', 'POST'])
@login_required
def application_settings(application_id):
    user = current_user
    application = get_application(application_id)
    
    application_settings = get_application_settings(user.user_id, application_id)
    if application_settings == None:
        application_settings = ApplicationSettings(user.user_id, application.application_id, {})
    
    default_domain = get_application_domain(user, application)

    form = ApplicationSettingsForm()
    if form.validate_on_submit():
        domain = form.domain.data.strip()
        if len(domain) != 0 and domain != default_domain:
            application_settings.settings["domain"] = domain
        else:
            application_settings.settings.pop("domain", None)
        update_application_settings(application_settings)
        return redirect(url_for('application_settings', application_id=application_id))

    form.domain.data = application_settings.settings.get("domain", default_domain)

    return render_template('application_settings.html', application=application, 
        application_settings=application_settings, form=form)
