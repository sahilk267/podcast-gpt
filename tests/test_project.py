import pytest
from podcast.project import sample_project, validate_project, text_fingerprint
from podcast.settings import SPEAKERS


def test_sample_is_valid():
    project = validate_project(sample_project())
    assert len(project['lines']) == 32
    assert set(x['speaker'] for x in project['lines']) == set(SPEAKERS)


def test_ids_unique_and_safe():
    project = sample_project()
    project['lines'][1]['id'] = project['lines'][0]['id']
    with pytest.raises(ValueError):
        validate_project(project)


def test_bad_speaker():
    project = sample_project()
    project['lines'][0]['speaker'] = '../test'
    with pytest.raises(ValueError):
        validate_project(project)


def test_fingerprint_changes_with_text():
    line = sample_project()['lines'][0]
    original = text_fingerprint(line, SPEAKERS[line['speaker']])
    changed = {**line, 'text': line['text'] + ' again'}
    assert text_fingerprint(changed, SPEAKERS[changed['speaker']]) != original
