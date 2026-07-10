# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Django signals for consent state changes."""

from django.dispatch import Signal

# Sent when consent is confirmed or revoked.
# Provides: email (str), consent_type (str), granted (bool), source (str)
consent_changed = Signal()
