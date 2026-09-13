# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.contrib import admin, messages

from django_agreements.models import (
    AgreementDefinition,
    AgreementVersion,
    Channel,
    ClauseSet,
    ConsentRecord,
    ObjectionEvent,
    OrderAgreementSnapshot,
)
from django_agreements.services import channel_service, clause_set_service


class AgreementVersionInline(admin.TabularInline):
    model = AgreementVersion
    extra = 0
    readonly_fields = ("version_number", "published_at", "is_current", "created_at")


@admin.register(AgreementDefinition)
class AgreementDefinitionAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "category", "consent_channel", "is_active", "is_system", "sort_order")
    list_filter = ("category", "consent_channel", "is_active", "is_system")
    search_fields = ["slug", "name"]
    ordering = ("sort_order", "name")
    filter_horizontal = ("channels",)
    inlines = [AgreementVersionInline]


@admin.register(AgreementVersion)
class AgreementVersionAdmin(admin.ModelAdmin):
    list_display = ("definition", "version_number", "is_current", "published_at", "created_at")
    list_filter = ("is_current",)
    search_fields = ["definition__slug", "definition__name"]
    readonly_fields = ("created_at",)


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = ("email", "agreement_version", "granted", "source", "channel_idx", "created_at")
    list_filter = ("granted", "source")
    search_fields = ["email"]
    readonly_fields = (
        "email",
        "customer_id",
        "agreement_version",
        "granted",
        "source",
        "ip_address",
        "user_agent",
        "channel_idx",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OrderAgreementSnapshot)
class OrderAgreementSnapshotAdmin(admin.ModelAdmin):
    list_display = ("order_id", "email", "agreement_version", "language", "granted", "created_at")
    search_fields = ["order_id", "email"]
    readonly_fields = (
        "order_id",
        "email",
        "agreement_version",
        "body_snapshot",
        "language",
        "granted",
        "ip_address",
        "user_agent",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.action(description="Sync channels from PIM")
def sync_channels_from_pim(modeladmin, request, queryset):
    count = channel_service.sync_channels_from_pim()
    modeladmin.message_user(request, f"Synced {count} channels from PIM.")


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ("idx", "name", "default_language")
    search_fields = ["idx", "name"]
    actions = [sync_channels_from_pim]


@admin.action(description="Publish selected")
def publish_clause_sets(modeladmin, request, queryset):
    published = 0
    for clause_set in queryset:
        try:
            clause_set_service.publish(clause_set, user=request.user)
            published += 1
        except ValueError as error:
            modeladmin.message_user(request, str(error), level=messages.ERROR)
    modeladmin.message_user(request, f"Published {published} clause sets.")


@admin.register(ClauseSet)
class ClauseSetAdmin(admin.ModelAdmin):
    list_display = ("channel", "legal_basis", "language", "version", "is_current", "published_at")
    list_filter = ("channel", "legal_basis", "language", "is_current")
    readonly_fields = ("version", "is_current", "published_at", "created_by")
    actions = [publish_clause_sets]

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return self.readonly_fields
        locked = (*self.readonly_fields, "channel", "legal_basis", "language")
        if obj.published_at:
            return (*locked, *clause_set_service.CLAUSE_FIELDS)
        return locked

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.published_at:
            return False
        return super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        if change:
            super().save_model(request, obj, form, change)
            return
        created = clause_set_service.create_version(
            channel=obj.channel,
            legal_basis=obj.legal_basis,
            language=obj.language,
            texts={field: getattr(obj, field) for field in clause_set_service.CLAUSE_FIELDS},
            user=request.user,
        )
        obj.pk, obj.version = created.pk, created.version


@admin.register(ObjectionEvent)
class ObjectionEventAdmin(admin.ModelAdmin):
    list_display = ("email", "channel", "source", "clause_set", "created_at")
    list_filter = ("source", "channel")
    search_fields = ["email"]
    readonly_fields = ("channel", "email", "source", "reason", "clause_set", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
