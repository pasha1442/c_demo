from decouple import config

def get_current_company_ref(request):
    company, langfuse_base_url, langfuse_project_id = None, None, None
    if request and request.user and request.user.is_authenticated:
        company = request.user.current_company
        if company:
            langfuse_project_id = company.langfuse_project_id
        langfuse_base_url = config('LANGFUSE_HOST', default="")
    return {"current_company": company,
            "langfuse_project_id": langfuse_project_id,
            "langfuse_base_url": langfuse_base_url}
