from django.http import JsonResponse
from django.views.decorators.http import require_GET

from allauth.socialaccount.models import SocialAccount


@require_GET
def current_user(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"detail": "Authentication credentials were not provided."},
            status=401,
        )

    email = request.user.email
    if not email:
        provider_account = (
            SocialAccount.objects.filter(user=request.user)
            .exclude(extra_data__email="")
            .first()
        )
        if provider_account:
            email = provider_account.extra_data.get("email", "")

    return JsonResponse(
        {
            "status": 200,
            "data": {
                "user": {
                    "id": request.user.pk,
                    "username": request.user.get_username(),
                    "email": email,
                }
            },
        }
    )
