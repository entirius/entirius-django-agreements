---
title: "Agreements: Database Diagrams"
description: "Auto-generated ER diagrams for the Agreements module."
sidebar:
  badge:
    text: "Auto-gen"
    variant: "note"
---

:::caution[Auto-generated]
These diagrams are auto-generated from Django model introspection.
Do not edit. Run `make erd` in entirius-docker to regenerate.
:::

## Agreements & Consent

```d2 layout=elk
Channel: {
  shape: sql_table
  style.fill: "#00ACC1"
  style.stroke: "#12141A"
  style.font-color: "#EBEDF2"
  id: int {constraint: primary_key}
  idx: varchar {constraint: unique}
  default_language_id: int {constraint: foreign_key}
  name: varchar
}

AgreementDefinition: {
  shape: sql_table
  style.fill: "#00ACC1"
  style.stroke: "#12141A"
  style.font-color: "#EBEDF2"
  id: int {constraint: primary_key}
  slug: varchar {constraint: unique}
  name: varchar
  category: varchar
  consent_channel: varchar
  content_route: varchar
  is_active: bool
  is_system: bool
}

AgreementVersion: {
  shape: sql_table
  style.fill: "#00ACC1"
  style.stroke: "#12141A"
  style.font-color: "#EBEDF2"
  id: int {constraint: primary_key}
  definition_id: int {constraint: foreign_key}
  version_number: int
  summary_t9n: jsonb
  content_published_id: int
  published_at: timestamp
  is_current: bool
}

ConsentRecord: {
  shape: sql_table
  style.fill: "#00ACC1"
  style.stroke: "#12141A"
  style.font-color: "#EBEDF2"
  id: int {constraint: primary_key}
  agreement_version_id: int {constraint: foreign_key}
  email: varchar
  customer_id: int
  granted: bool
  source: varchar
  ip_address: varchar
  user_agent: text
}

OrderAgreementSnapshot: {
  shape: sql_table
  style.fill: "#00ACC1"
  style.stroke: "#12141A"
  style.font-color: "#EBEDF2"
  id: int {constraint: primary_key}
  agreement_version_id: int {constraint: foreign_key}
  order_id: uuid
  email: varchar
  body_snapshot: text
  language: varchar
  granted: bool
  ip_address: varchar
}

Language: {
  shape: sql_table
  style.fill: "#484B57"
  style.stroke: "#1A1C25"
  style.stroke-dash: 3
  style.font-color: "#9A9CAA"
  id: int {constraint: primary_key}
  label: "Language (External: django_regional)"
}



Channel.default_language_id -> Language.id: {style.stroke: "#484B57"}

Channel.id <-> Language.id: {style.stroke: "#484B57"}

AgreementDefinition.id <-> Channel.id: {style.stroke: "#00ACC1"}

AgreementVersion.definition_id -> AgreementDefinition.id: {style.stroke: "#00ACC1"}

ConsentRecord.agreement_version_id -> AgreementVersion.id: {style.stroke: "#00ACC1"}

OrderAgreementSnapshot.agreement_version_id -> AgreementVersion.id: {style.stroke: "#00ACC1"}
```
