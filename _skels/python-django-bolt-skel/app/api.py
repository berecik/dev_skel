"""BoltAPI endpoints for the django-bolt skeleton service.

Routing is handled directly by the django-bolt Rust layer via the decorators
below; the Django ROOT_URLCONF (`app.urls`) is intentionally empty.
"""

# `typing.List` is used (instead of the built-in `list[...]` syntax)
# inside ViewSet `list` action annotations because Python 3.14's lazy
# annotation evaluator (PEP 649) resolves the bare name `list` from
# the *class* scope and finds the just-defined `list` method shadowing
# the builtin, raising `TypeError: 'function' object is not subscriptable`.
# `List` from typing is unaffected.
from typing import List

import msgspec
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from django_bolt import (
    AllowAny,
    BoltAPI,
    IsAuthenticated,
    JSON,
    JWTAuthentication,
    ModelViewSet,
    PageNumberPagination,
    Request,
    action,
    get_current_user,
)

from app.models import Item, Project, ReactState, Task, UserProfile
from app.schemas import (
    ItemCreateSchema,
    ItemSchema,
    LoginSchema,
    OAuthLoginSchema,
    ProjectCreateSchema,
    ProjectSchema,
    ReactStateUpsertSchema,
    RefreshSchema,
    RegisterSchema,
    TaskCreateSchema,
    TaskDetailSchema,
    TaskSchema,
    UserProfileSchema,
)
from app.services.auth_service import AuthService

api = BoltAPI()


# --------------------------------------------------------------------------- #
#  Authentication
# --------------------------------------------------------------------------- #


@api.post("/api/auth/register", guards=[AllowAny()])
async def register(request: Request) -> dict:
    data = msgspec.json.decode(request.body, type=RegisterSchema)
    if data.password != data.password_confirm:
        return JSON({"error": "Passwords do not match"}, status_code=400)
    # `.aexists()` is the async-safe queryset method (Django 4.2+);
    # the regular `.exists()` would trip Django's
    # SynchronousOnlyOperation guard from inside this async view.
    if await User.objects.filter(username=data.username).aexists():
        return JSON({"error": "Username already exists"}, status_code=400)
    # `AuthService.register_user` is intentionally sync so the unit
    # tests in `app/tests/test_models.py` can call it directly without
    # needing pytest-asyncio. Wrap it with `sync_to_async` here so
    # Django's async-safety guard is satisfied at the view boundary.
    user = await sync_to_async(AuthService.register_user)(
        data.username, data.email, data.password
    )
    return JSON(
        {"user": {"id": user.id, "username": user.username, "email": user.email}},
        status_code=201,
    )


@api.post("/api/auth/login", guards=[AllowAny()])
async def login(request: Request) -> dict:
    data = msgspec.json.decode(request.body, type=LoginSchema)
    result = await sync_to_async(AuthService.authenticate_user)(
        data.username, data.password
    )
    if result is None:
        return JSON({"error": "Invalid credentials"}, status_code=401)
    return JSON(result)


@api.post("/api/auth/oauth", guards=[AllowAny()])
async def oauth_login(request: Request) -> dict:
    data = msgspec.json.decode(request.body, type=OAuthLoginSchema)
    if data.provider not in ("google", "apple"):
        return JSON({"error": "Invalid provider"}, status_code=400)
    result = await sync_to_async(AuthService.oauth_login)(
        data.provider, data.access_token
    )
    return JSON(result)


@api.post("/api/auth/refresh", guards=[AllowAny()])
async def refresh(request: Request) -> dict:
    data = msgspec.json.decode(request.body, type=RefreshSchema)
    result = await sync_to_async(AuthService.refresh_tokens)(data.refresh)
    if result is None:
        return JSON({"error": "Invalid token"}, status_code=401)
    return JSON(result)


@api.get(
    "/api/auth/profile",
    auth=[JWTAuthentication()],
    guards=[IsAuthenticated()],
)
async def get_profile(request: Request) -> UserProfileSchema:
    user = await get_current_user(request)
    profile = await UserProfile.objects.select_related("user").aget(user=user)
    return UserProfileSchema.from_model(profile)


@api.patch(
    "/api/auth/profile",
    auth=[JWTAuthentication()],
    guards=[IsAuthenticated()],
)
async def update_profile(request: Request) -> UserProfileSchema:
    user = await get_current_user(request)
    body = msgspec.json.decode(request.body)
    profile = await UserProfile.objects.aget(user=user)
    profile.bio = body.get("bio", profile.bio)
    profile.avatar_url = body.get("avatar_url", profile.avatar_url)
    await profile.asave()
    return UserProfileSchema.from_model(profile)


# --------------------------------------------------------------------------- #
#  Project CRUD
# --------------------------------------------------------------------------- #


@api.viewset(
    "/api/projects",
    auth=[JWTAuthentication()],
    guards=[IsAuthenticated()],
)
class ProjectViewSet(ModelViewSet):
    serializer_class = ProjectSchema
    pagination_class = PageNumberPagination

    async def get_queryset(self):
        user = await get_current_user(self.request)
        return Project.objects.filter(owner=user).select_related("owner")

    async def list(self, request: Request) -> List[ProjectSchema]:
        qs = await self.get_queryset()
        return [ProjectSchema.from_model(obj) async for obj in qs]

    async def create(self, request: Request) -> ProjectSchema:
        data = msgspec.json.decode(request.body, type=ProjectCreateSchema)
        user = await get_current_user(request)
        project = await Project.objects.acreate(
            name=data.name, description=data.description, owner=user
        )
        return JSON(ProjectSchema.from_model(project), status_code=201)

    async def retrieve(self, request: Request, pk: int) -> ProjectSchema:
        qs = await self.get_queryset()
        project = await qs.aget(pk=pk)
        return ProjectSchema.from_model(project)

    async def destroy(self, request: Request, pk: int) -> dict:
        qs = await self.get_queryset()
        project = await qs.aget(pk=pk)
        await project.adelete()
        return JSON({}, status_code=204)


# --------------------------------------------------------------------------- #
#  Task CRUD
# --------------------------------------------------------------------------- #


@api.viewset(
    "/api/tasks",
    auth=[JWTAuthentication()],
    guards=[IsAuthenticated()],
)
class TaskViewSet(ModelViewSet):
    serializer_class = TaskSchema
    pagination_class = PageNumberPagination

    async def get_queryset(self):
        user = await get_current_user(self.request)
        return Task.objects.filter(project__owner=user).select_related(
            "project", "assignee"
        )

    async def list(self, request: Request) -> List[TaskSchema]:
        qs = await self.get_queryset()
        return [TaskSchema.from_model(obj) async for obj in qs]

    async def create(self, request: Request) -> TaskSchema:
        data = msgspec.json.decode(request.body, type=TaskCreateSchema)
        user = await get_current_user(request)
        project = await Project.objects.filter(owner=user).aget(pk=data.project)
        task = await Task.objects.acreate(
            title=data.title,
            description=data.description,
            project=project,
            assignee_id=data.assignee,
            priority=data.priority,
            status=data.status,
        )
        return JSON(TaskSchema.from_model(task), status_code=201)

    async def retrieve(self, request: Request, pk: int) -> TaskDetailSchema:
        qs = await self.get_queryset()
        task = await qs.aget(pk=pk)
        return TaskDetailSchema.from_model(task)

    @action(methods=["PATCH"], detail=True)
    async def assign(self, request: Request, pk: int) -> TaskDetailSchema:
        body = msgspec.json.decode(request.body)
        assignee_id = body.get("assignee_id")
        try:
            assignee = await User.objects.aget(pk=assignee_id)
        except User.DoesNotExist:
            return JSON({"error": "User not found"}, status_code=404)
        qs = await self.get_queryset()
        task = await qs.aget(pk=pk)
        task.assignee = assignee
        await task.asave()
        return TaskDetailSchema.from_model(task)

    @action(methods=["PATCH"], detail=True)
    async def complete(self, request: Request, pk: int) -> TaskDetailSchema:
        qs = await self.get_queryset()
        task = await qs.aget(pk=pk)
        task.is_completed = True
        task.status = "done"
        await task.asave()
        return TaskDetailSchema.from_model(task)


# --------------------------------------------------------------------------- #
#  Wrapper-shared `items` resource (consumed by the React skeleton).
# --------------------------------------------------------------------------- #
#
# This viewset talks to the canonical wrapper-shared `items` table —
# see `app/models.py::Item` and the schema convention documented in
# `_docs/SHARED-DATABASE-CONVENTIONS.md`. The frontend (React skeleton)
# calls `${BACKEND_URL}/api/items` against it by default.


@api.viewset(
    "/api/items",
    auth=[JWTAuthentication()],
    guards=[IsAuthenticated()],
)
class ItemViewSet(ModelViewSet):
    serializer_class = ItemSchema
    pagination_class = PageNumberPagination

    async def get_queryset(self):
        return Item.objects.all()

    async def list(self, request: Request) -> List[ItemSchema]:
        qs = await self.get_queryset()
        return [ItemSchema.from_model(obj) async for obj in qs]

    async def create(self, request: Request) -> ItemSchema:
        data = msgspec.json.decode(request.body, type=ItemCreateSchema)
        item = await Item.objects.acreate(
            name=data.name,
            description=data.description,
            is_completed=data.is_completed,
        )
        return JSON(ItemSchema.from_model(item), status_code=201)

    async def retrieve(self, request: Request, pk: int) -> ItemSchema:
        qs = await self.get_queryset()
        item = await qs.aget(pk=pk)
        return ItemSchema.from_model(item)

    @action(methods=["POST"], detail=True)
    async def complete(self, request: Request, pk: int) -> ItemSchema:
        item = await Item.objects.aget(pk=pk)
        item.is_completed = True
        await item.asave()
        return ItemSchema.from_model(item)


# --------------------------------------------------------------------------- #
#  React state save/load (`/api/state`)
# --------------------------------------------------------------------------- #
#
# Per-user JSON key/value store. The React skeleton's
# `src/state/state-api.ts` calls these to persist UI state (filters,
# sort order, preferences) across sessions. The shape is intentionally
# opaque — the backend never parses `value`, it just round-trips the
# string.


@api.get(
    "/api/state",
    auth=[JWTAuthentication()],
    guards=[IsAuthenticated()],
)
async def react_state_load(request: Request) -> dict:
    """Return every state slice for the current user as a single dict."""

    user = await get_current_user(request)
    payload: dict[str, str] = {}
    async for entry in ReactState.objects.filter(user=user):
        payload[entry.key] = entry.value
    return payload


@api.put(
    "/api/state/{key}",
    auth=[JWTAuthentication()],
    guards=[IsAuthenticated()],
)
async def react_state_upsert(request: Request, key: str) -> dict:
    """Upsert a single state slice for the current user."""

    user = await get_current_user(request)
    body = msgspec.json.decode(request.body, type=ReactStateUpsertSchema)
    await ReactState.objects.aupdate_or_create(
        user=user,
        key=key,
        defaults={"value": body.value},
    )
    return {"key": key, "value": body.value}


@api.delete(
    "/api/state/{key}",
    auth=[JWTAuthentication()],
    guards=[IsAuthenticated()],
)
async def react_state_delete(request: Request, key: str) -> dict:
    """Drop a single state slice (if it exists) for the current user."""

    user = await get_current_user(request)
    deleted, _ = await ReactState.objects.filter(user=user, key=key).adelete()
    return {"key": key, "deleted": bool(deleted)}
