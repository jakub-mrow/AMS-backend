from ams.tasks import add


def test_example_task():
    result = add.delay(3, 2)
    assert result.get() == 5