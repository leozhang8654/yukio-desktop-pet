"""Async acknowledgements must not dismiss the question; other tools may keep running."""
import unittest
from yukio.parsers_codex import CodexRolloutParser
from yukio.events import Kind, PetState
from yukio.router import ActivityRouter
from yukio.answer import AnswerDelivery, Backend, CLIPBOARD_CHANGED, COPIED, SETTLE_MS


class QuestionLifecycleTests(unittest.TestCase):
    def event(self, parser, payload):
        return parser.events({"type":"response_item", "payload":payload}, 1000)

    def start(self, parser, async_=True):
        return self.event(parser, {"type":"function_call", "call_id":"q", "name":"request_user_input_async" if async_ else "request_user_input",
                                  "arguments":{"questions":[{"title":"Color?", "options":["Blue","Green"]}]}})

    def test_question_survives_ack_and_parallel_work_until_answer(self):
        p = CodexRolloutParser("test"); router = ActivityRouter(now=1000)
        for e in self.start(p): router.ingest(e,1000)
        self.assertEqual(self.event(p,{"type":"function_call_output","call_id":"q","output":'{"accepted":true}'}),[])
        for e in self.event(p,{"type":"function_call","call_id":"work","name":"exec_command","arguments":{"cmd":"ls"}}): router.ingest(e,1000)
        for t in range(1000,5100,100): router.tick(t)
        self.assertEqual(router.displayed,PetState.question_for_user)
        self.assertEqual(router.asking_question.question.text,"Color?")
        answer = self.event(p,{"type":"message","role":"user","content":"Blue"})
        self.assertEqual([e.kind for e in answer],[Kind.activity_end,Kind.task_start])
        for e in answer: router.ingest(e,5100)
        for t in range(5100,8100,100): router.tick(t)
        self.assertIsNone(router.asking_question)

    def test_structured_reply_closes_without_a_new_turn(self):
        p=CodexRolloutParser("test");self.start(p)
        answer=self.event(p,{"type":"message","role":"user","content":"<send_user_message_question_reply>Blue</send_user_message_question_reply>"})
        self.assertEqual([e.kind for e in answer],[Kind.activity_end])

    def test_sync_result_closes_and_abort_drops_async_tracking(self):
        p=CodexRolloutParser("test");self.start(p,False)
        self.assertEqual(self.event(p,{"type":"function_call_output","call_id":"q","output":'{"answers":{}}'})[0].kind,Kind.activity_end)
        self.start(p)
        p.events({"type":"event_msg","payload":{"type":"turn_aborted","reason":"interrupted"}},1100)
        self.assertEqual([e.kind for e in self.event(p,{"type":"message","role":"user","content":"next"})],[Kind.task_start])

    def test_clipboard_change_cancels_without_typing(self):
        sequence=[1];typed=[]
        backend=Backend(lambda:"Codex.exe",lambda s:typed.append(s) or True,lambda:True,lambda s:True,lambda:sequence[0])
        delivery=AnswerDelivery(backend);delivery.start("Blue","Codex.exe",lambda:None,0)
        delivery.tick(0);sequence[0]+=1
        self.assertEqual(delivery.tick(SETTLE_MS+1),CLIPBOARD_CHANGED)
        self.assertEqual(typed,[])

    def test_focus_loss_after_typing_prevents_enter(self):
        front=["Codex.exe"];returns=[]
        def send(text): front[0]="notepad.exe";return True
        delivery=AnswerDelivery(Backend(lambda:front[0],send,lambda:returns.append(1) or True,lambda s:True))
        delivery.start("Blue","Codex.exe",lambda:None,0);delivery.tick(0)
        self.assertEqual(delivery.tick(SETTLE_MS+1),COPIED)
        self.assertEqual(returns,[])
