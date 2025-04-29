from company.utils import CompanyUtils
from services.services.rest_api_agent import RestAPIAgent
import asyncio
from asgiref.sync import sync_to_async

class BaseAgent:

    def __init__(self, company, agent_slug):
        self.AGENT_CHOICES = {"api_agent": RestAPIAgent()}
        self.company = company
        self.agent_slug = agent_slug
        if company:
            CompanyUtils.set_company_registry(company)

    def invoke_agent(self, args, ai_args, custom_headers={}, company=None):
        return asyncio.run(self.async_invoke_agent(args, ai_args, custom_headers, self.company))

    async def async_invoke_agent(self, args, ai_args, custom_headers, company=None):
        if self.agent_slug and self.company:
            _agent_slug = self.agent_slug.split(".")
            _ag_type_slug = _agent_slug[0] if len(_agent_slug) else None
            _ag_slug = _agent_slug[1] if len(_agent_slug) > 1 else None
            if _ag_slug and _ag_type_slug:
                """ ag_obj = Agent Object"""
                _ag_obj = self.AGENT_CHOICES[_ag_type_slug]
                if _ag_obj:
                    _ag_res = await sync_to_async(_ag_obj.invoke_agent)( slug=_ag_slug, args=args,
                                                      ai_args=ai_args, custom_headers=custom_headers, company=company )
                    # _ag_res = await asyncio.to_thread(_ag_obj.invoke_agent, slug=_ag_slug, args=args,
                    #                                  ai_args=ai_args, custom_headers=custom_headers, company=company)

                    return _ag_res
        return None

