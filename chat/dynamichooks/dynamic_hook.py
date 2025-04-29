from chat.dynamichooks.summary_generator_dynamic_hook import SummaryGeneratorDynamicHook


class DynamicHook:
    PROCESSORS = {
        'summary_generation' : SummaryGeneratorDynamicHook()
    }
    
    def __init__(self, state, company=None):
        self.processor = self.PROCESSORS[state['hook_type']]
        self.state = state
        self.company = company
        
    async def process(self):
        await self.processor.process(company=self.company, state=self.state)
        
    def publish(self):
        self.processor.publish(self.state)