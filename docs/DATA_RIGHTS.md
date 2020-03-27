# Source rights and acquired scope

Reviewed on 2026-11-11. This is an engineering acquisition decision, not a legal opinion. Code is MIT licensed. Authored fixture facts and fictional names are CC0. Those licenses do not apply to external football data.

| Source | Intended use | Acquired | Redistribution | Current decision |
| --- | --- | --- | --- | --- |
| Authored fixture | Mechanical replay and UI | 1 fictional fixture, 24 fictional roster entries | CC0 | Shipped, visibly synthetic |
| StatsBomb open data | Local noncommercial research | License and schema reviewed, no actual event corpus acquired | Raw-data distribution restricted by agreement | Adapter available for operator-authorized local files |
| Juventus official release | Fee-case audit | One manually transcribed factual observation | Article/PDF not copied | Citation and separated guaranteed/optional terms |
| Ajax official release | Fee-case audit | One manually transcribed factual observation | Article/images not copied | Citation and guaranteed/optional terms |
| Licensed actual live feed | Live integration | None | Unknown | Blocked |
| Europe lower-division registers | Registry denominator | None | Unknown per federation | Blocked |
| Independent clips and ratings | Blinded review | None | Unknown | Blocked |

The [StatsBomb repository](https://github.com/hudl/open-data) redirects from its earlier organization. Its [public data user agreement](https://github.com/hudl/open-data/blob/master/LICENSE.pdf) limits use and distribution. The terms reviewed at repository commit `4b73468fc5b0f1950f9f66fada70ad3a4f9327cb` restrict redistribution of raw data and commercial exploitation, and require brand attribution for published analysis. A public GitHub repository is not a blanket license for a live redistribution service. No StatsBomb raw files, logo, player analysis or downloaded model are included here.

The two [official fee records](../fixtures/official-deals.json) retain source URLs. The [Juventus release](https://www.juventus.com/images/image/private/fl_attachment/dev/tjgrao8qrtwkpmpmzyne.pdf) separates EUR 51.3 million consideration, up to EUR 3.4 million ancillary costs, and up to EUR 6 million conditional bonuses. The [Ajax completion release](https://english.ajax.nl/articles/transfer-antony-matheus-dos-santos-completed/) separates EUR 95 million guaranteed consideration from a possible total EUR 100 million. Those examples do not constitute a linked training corpus, establish transaction comparability, or authorize bulk collection. Publication times are not supplied, so known-at timestamps conservatively use the end of the publication day.

Initial competition targets are the top domestic divisions of England, Spain, Germany, Italy and France plus UEFA club fixtures. Acquired actual event matches for all six targets: zero. No season/field matrix is inferred from the targets. The registry target uses the [55 UEFA member associations](https://www.uefa.com/nationalassociations/), checked on the review date. Divisions, eligible seasons, youth/reserve inclusion and registered-player denominators remain unreconciled. The UI reports that gap rather than treating 55 as a player coverage denominator.

Operator-supplied archives remain under ignored `data/`. Import requires an explicit local-research rights declaration and preserves absent provider publication times. Saved current archives do not reconstruct historical live revisions. Commercial or actual-live use requires a separate authorized source with explicit redistribution scope and freshness SLO. No purchases or subscriptions are configured.
