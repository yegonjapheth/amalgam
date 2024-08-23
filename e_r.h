{% extends "base.html" %}

{% block title %}Exam Results{% endblock %}

{% block content %}
<h1>Results for {{ exam.exam_subject }}</h1>

<h2>Average Score: <strong>{{ average_score }}</strong></h2>

<!-- <h2>Results Chart</h2> -->
<div>{{ graph_html|safe }}</div>

<h2>Results</h2>
<table class="exam_results">
    <thead>
        <tr>
	    <th>S/No</th>
            <th>Learner</th>
            <th>Score</th>
        </tr>
    </thead>
    <tbody>
        {% for result in results %}
        <tr>
	    <td>{{ loop.index }}</td>
            <td>{{ result.learner.learner_name }}</td>
            <td>{{ result.result_score }}</td>
        </tr>
        {% endfor %}
    </tbody>
</table>
<br><br>
{% endblock %}
