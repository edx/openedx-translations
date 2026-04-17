Migrating from Transifex to ai-translations
###########################################

Status
******

In Progress.

Context
*******

As of `OEP-58`_, the `Transifex GitHub App`_ has been used to sync translations
between Transifex projects and the openedx-translations repository. Transifex is
a third-party translation management platform that provides human translation
services and automated synchronization.

The translation workflow has two distinct file formats:

- ``.po`` files — used by Python/Django applications
- ``.json`` files — used by JavaScript/React frontend applications

Problem
*******

As part of the ongoing effort to decouple from openedx (see `0003-fork-from-openedx`_),
we also need to decouple our string translations from openedx.

In particular, as our user-facing text diverges from openedx, we need a separate sandbox
for source strings and their translations.

.. _0003-fork-from-openedx: 0003-fork-from-openedx.rst

Decision
********

Migrate translation management from Transifex to the internal `ai-translations`_
service. The migration is being done incrementally:

1. **JavaScript/frontend apps** — Migrated first. The ``translate-source-strings.yml``
   workflow calls the ai-translations service API to fetch translated ``.json`` files
   for ~22 frontend applications across ~21 languages.

2. **Python/Django apps** — Remaining on Transifex during the transition. These
   continue to sync via the `Transifex GitHub App`_ and the existing
   ``automerge-transifex-app-prs.yml`` workflow.

Consequences
************

``ai-translations`` will have to be extended to support the features we currently rely
on in Transifex. Namely, translation of strings (including variable injection, pluralization,
etc.) and quality control (e.g. validation, translator review, etc.).

**Positive**

* Much greater control of the translation process, including how strings are translated
  and the ability to directly integrate with internal tooling and workflows.
* Removal of the need to pay for an enterprise license for Transifex, which is a
  significant cost saving.

**Negative / Trade-offs**

* Development and maintenance of the ai-translations service will be an ongoing cost,
  and we will need to ensure it meets our needs in terms of features and quality control.

Alternatives Considered
***********************

Staying on Transifex
====================

While strings continue to be translated by Transifex in the upstream openedx/openedx-translations
repository, edX no longer maintains a license with Transifex, so we cannot translate
edX-specific strings.

Using Transifex would require either leveraging the existing openedx translations, which are expected
to diverge, or paying for a new, costly enterprise license for the edX org.

Rollout Plan
************

Separately, develop ai-translations to support ``JSON`` and ``PO`` translations. First,
``JSON``, since it is a simpler format, then ``PO``.

In parallel, update workflows in this repository to fetch translations from ai-translations
for JavaScript/frontend apps, then for Python/Django apps once ai-translations supports it.

.. _OEP-58: https://open-edx-proposals.readthedocs.io/en/latest/architectural-decisions/oep-0058-arch-translations-management.html
.. _Transifex GitHub App: https://github.com/apps/transifex-integration
.. _ai-translations: https://github.com/edx/ai-translations
