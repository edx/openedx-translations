Fork openedx-translations from Open edX
########################################

Status
******

Complete

Context
*******

This repository was originally established under the `openedx`_ GitHub organization
as part of `OEP-58`_, serving as the central translations hub for the broader Open edX
community. It was used to sync translation files between Open edX repositories and
Transifex.

edX has historically relied on the upstream `openedx/openedx-translations`_ repository
for its translation workflows, sharing infrastructure and release cadence with the Open
edX community project.

Problem
*******

As edX decouples its repositories from the Open edX GitHub organization, shared
infrastructure creates friction around feature development and release cadence. Relying
on the upstream openedx repository means:

- Feature work must align with Open edX community priorities and review processes
- Release timing is tied to Open edX release cycles rather than edX's own schedule
- Internal tooling (such as `ai-translations`_) cannot be deeply integrated without
  upstream coordination

Decision
********

Fork `openedx/openedx-translations`_ into the `edx`_ GitHub organization as
``edx/openedx-translations``. The fork allows edX to:

- Iterate on translation tooling independently (e.g. integrating `ai-translations`_)
- Control release cadence and branch strategy without upstream coordination
- Maintain the same foundational structure (OEP-58 compliance, ``translations/``
  directory layout, openedx-atlas compatibility) while diverging where needed

Consequences
************

**Positive**

* Full control over feature development and release cadence
* Ability to integrate internal tooling (ai-translations) without upstream dependency
* Faster iteration on translation workflows

**Negative / Trade-offs**

* Changes to the upstream openedx repository will not automatically flow into this fork
  and must be manually cherry-picked if needed, or replaced with internal changes

Relationship to Upstream
************************

The goal here is a hard fork from `openedx/openedx-translations`_. After the fork, there
will be no ongoing synchronization of code or translation files between the two repositories.
This allows edX to diverge as needed while maintaining the same foundational structure.

.. _OEP-58: https://open-edx-proposals.readthedocs.io/en/latest/architectural-decisions/oep-0058-arch-translations-management.html
.. _openedx: https://github.com/openedx
.. _edx: https://github.com/edx
.. _openedx/openedx-translations: https://github.com/openedx/openedx-translations
.. _ai-translations: https://github.com/edx/ai-translations
