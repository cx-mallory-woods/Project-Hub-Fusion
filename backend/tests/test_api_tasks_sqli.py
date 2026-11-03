"""
Regression tests for SQL injection in GET /api/v1/tasks (get_tasks_api)
"""
import pytest
from models import db, Task


@pytest.fixture
def two_tasks(db_session, sample_project, sample_user):
    """Create two tasks with distinct titles"""
    t1 = Task(title='Alpha job', description='first', project_id=sample_project.id,
              assigned_to=sample_user.id, created_by=sample_user.id,
              status='pending', priority='medium')
    t2 = Task(title='Beta job', description='second', project_id=sample_project.id,
              created_by=sample_user.id, status='pending', priority='medium')
    db_session.add_all([t1, t2])
    db_session.commit()
    return t1, t2


def _titles(response):
    return sorted(t['title'] for t in response.get_json()['tasks'])


def test_search_returns_matching_tasks(client, two_tasks):
    response = client.get('/api/v1/tasks?search=Alpha')
    assert response.status_code == 200
    assert _titles(response) == ['Alpha job']


def test_search_with_project_and_assignee_filters(client, two_tasks, sample_project, sample_user):
    response = client.get(
        f'/api/v1/tasks?search=job&project_id={sample_project.id}&assigned_to={sample_user.id}')
    assert response.status_code == 200
    assert _titles(response) == ['Alpha job']


@pytest.mark.parametrize('payload', [
    "' OR '1'='1",
    "%' OR 1=1 --",
    "x'; DROP TABLE tasks; --",
])
def test_search_injection_is_treated_as_literal(client, two_tasks, payload):
    response = client.get('/api/v1/tasks', query_string={'search': payload})
    assert response.status_code == 200
    assert response.get_json()['tasks'] == []
    # The table must still exist and be intact
    assert db.session.query(Task).count() == 2


@pytest.mark.parametrize('param', ['project_id', 'assigned_to'])
def test_id_filter_injection_is_not_executed(client, two_tasks, param):
    response = client.get(
        '/api/v1/tasks',
        query_string={'search': 'job', param: '1 OR 1=1'})
    assert response.status_code == 200
    assert response.get_json()['tasks'] == []
    assert db.session.query(Task).count() == 2


def test_like_wildcards_are_escaped(client, two_tasks):
    response = client.get('/api/v1/tasks', query_string={'search': '%'})
    assert response.status_code == 200
    assert response.get_json()['tasks'] == []
