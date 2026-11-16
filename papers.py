"""" pastpapers practice: caftalog, attempt,  AI marking, mistake log."""
import json
import os
import uuid

from flask import (Blueprint, abort, current_app, flash, redirect, render_template, request, url_for)
from flask_login import current_user, login_required

from models import Attempt, Mistake, Paper, Subject, db
from tagging import grade_answer

papers = Blueprint("papers", __name__)

def _upload(field, allowed):