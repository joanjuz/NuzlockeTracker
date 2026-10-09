import unittest
import queue
from unittest.mock import patch
from app import App
class Var:
 def __init__(self,value=None):self.value=value
 def get(self):return self.value
 def set(self,value):self.value=value
class Reader:
 def __init__(self,port=0):self.closed=False;self.resumed=False
 def identify(self):return 'OK'
 def close(self):self.closed=True
 def resume(self):self.resumed=True
class LifecycleTests(unittest.TestCase):
 def make(self):
  a=App.__new__(App);a.progress_queue=queue.SimpleQueue();a.reader=Reader();a.ready=True;a.scan=[1,2];a.retry_delay=2;a.had_session=True;a.busy=False;a.was_running=True
  for k in ['connection','team_status','box_status','status']:setattr(a,k,Var())
  a.port=Var('24689');a.boxes={1:[]};a.box_bytes={1:b'x'};a.box_times={1:'old'};a.reconnect=Var(True)
  a.render_boxes=lambda:None;a.run=lambda op,done:done(op());return a
 def test_transport_loss_marks_stale(self):
  a=self.make();r=a.reader;a.transport_error(ConnectionError('lost'))
  self.assertTrue(r.closed);self.assertIsNone(a.reader);self.assertFalse(a.ready);self.assertEqual(a.scan,[])
  self.assertIn('anteriores',a.team_status.get());self.assertEqual(a.retry_delay,4)
 def test_reconnect_clears_box_cache_and_resumes(self):
  a=self.make()
  with patch('app.LimeGDB',Reader):a.connect(automatic=True)
  self.assertTrue(a.reader.resumed);self.assertTrue(a.ready);self.assertEqual(a.boxes,{})
 def test_manual_connection_waits_for_continue(self):
  a=self.make()
  with patch('app.LimeGDB',Reader):a.connect()
  self.assertFalse(a.reader.resumed);self.assertFalse(a.ready)
 def test_explicit_disconnect_disables_retry(self):
  a=self.make();a.disconnect();self.assertFalse(a.reconnect.get());self.assertFalse(a.had_session);self.assertIsNone(a.reader)
 def test_cancel_keeps_loaded_boxes(self):
  a=self.make();a.cancel_scan();self.assertEqual(a.scan,[]);self.assertIn(1,a.boxes)

 def test_heartbeat_releases_halt_on_existing_socket(self):
  a=self.make();a.heartbeat_at=0;a.heartbeat()
  self.assertTrue(a.reader.resumed)
  self.assertGreater(a.heartbeat_at,0)
  self.assertIn('supervisada',a.connection.get())

 def test_error_discards_old_progress(self):
  a=self.make();a.progress_queue.put('Localizando RAM: 520 MB')
  a.transport_error(ConnectionError('falló la búsqueda'))
  self.assertTrue(a.progress_queue.empty())
  self.assertIn('falló la búsqueda',a.status.get())
