from .testing_model import SampleModel
from ..events import BaseEvent


def test_event_dispatch():
    event = SampleEvent(obj=SampleModel(id=1, name='test'))
    event.dispatch()
    assert event.name == 'sample'
    assert event.obj == SampleModel(id=1, name='test')
    assert event.__class__.__name__ == 'SampleEvent'



class SampleEvent(BaseEvent[SampleModel]):
    def _dispatch(self, **kwargs):
        print('dispatching event:', self.__event_name__)
        print('obj:', self.obj)
