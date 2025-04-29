from chat.dynamichooks.summary_generator_dynamic_hook import SummaryGeneratorDynamicHook
from chat.dynamichooks.hooks.snooping_incoming_msg_hook import SnoopingIncomingMsgHook
from chat.dynamichooks.hooks.snooping_outgoing_msg_hook import SnoopingOutgoingMsgHook


class DynamicHook:
    # PROCESSORS = {
    #     'summary_generation' : SummaryGeneratorDynamicHook()
    # }
    
    def __init__(self, state, company=None):
        # self.processor = self.PROCESSORS[state['hook_type']]
        # self.state = state
        # self.company = company
        self.hook_processors = {
            'summary_generation': SummaryGeneratorDynamicHook(),
            'snooping_incoming_msg': SnoopingIncomingMsgHook(),
            'snooping_outgoing_msg': SnoopingOutgoingMsgHook()
            }
        
        self.state = state
        self.company = company
        self.hook_type = state.get('hook_type')
        
        if self.hook_type in self.hook_processors:
            self.processor = self.hook_processors[self.hook_type]
        else:
            raise ValueError(f"Unknown hook type: {self.hook_type}")
        
    async def process(self):
        await self.processor.process(company=self.company, state=self.state)
        
    def publish(self):
        self.processor.publish(self.state)