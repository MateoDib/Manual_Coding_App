# Coding Protocol

## Publication Context

This protocol accompanies the open-science release for **"Using AI-led semi-structured interviews to explore the connection between Carbon Tax narratives and climate anxiety"** by **Matéo Dib, Thibaut Arpinon, and Bérangère Legendre**.

It explains how the project moved from qualitative interview material to **DAG-compatible topic sequences**. The method can be reused in other projects, but topic labels, phase rules, and ending nodes should be adapted to the new research question.

## Purpose

The aim is not only to assign topics. Each coded response is represented as an ordered sequence of tokens that preserves the structure of a participant's reasoning:

- causal or consequential chains;
- definitions and framings;
- distinct narrative paths;
- additive policy packages;
- coexisting concerns;
- priority or trade-off relations;
- information sources;
- actor-specific scope qualifiers;
- final acceptability or affective endpoints.

These sequences can be interpreted qualitatively and can later be translated into graph-like or DAG-style representations.

## Token Types

| Token type | Example | Interpretation |
|---|---|---|
| Substantive topic | `carbon_tax`, `fuel_price_increase` | A conceptual node in the participant's reasoning. |
| Causal or logical operator | `-->` | A positive link: `A --> B` means that A leads to B in the response. |
| Definition operator | `=` | `A = B` means that the participant defines or frames A as B. |
| Distinct path separator | `;` | Separates two narrative components within the same response. |
| Additive operator | `+` | `A + B` means that A and B form a combined policy, package, or bundle. |
| Coexistence operator | `&` | `A & B` means that A and B coexist without additive meaning. |
| Priority operators | `<`, `>` | `A < B` means B prevails over A; `A > B` means A prevails over B. |
| Source marker | <code>&#124;</code> | `A --> B \| newspaper` records an information source. |
| Aggregated topic | `green_transport_development (electric_vehicle_infrastructure, soft_mobility)` | A broad topic with more specific subtopics. |
| Scope-qualified topic | `fuel_price_increase[others]` | A topic qualified by the actor, group, or standpoint concerned. |

The source-marker row uses the HTML entity `<code>&#124;</code>` so Markdown does not interpret the coding symbol as a table separator.

## Normalization Rules

Substantive topics are lowercased. Multi-word concepts use underscores:

```text
future_environmental_benefits
purchasing_power_loss
economic_environmental_trade_off
```

The apps also accept typed labels with spaces and normalize them to underscore-separated labels.

## Directional Topic Labels

The arrow `-->` always encodes a positive causal or logical relation. The direction of variation must be placed in the topic label itself.

Prefer:

```text
fuel_price_increase
fuel_price_decrease
inflation
deflation
purchasing_power_loss
purchasing_power_gain
carbon_emission_reduction
carbon_emission_increase
```

Avoid neutral labels such as `fuel_price`, `price_level`, or `carbon_emissions` when the direction of change matters.

Example:

```text
carbon_tax --> fuel_price_increase --> unacceptability
carbon_tax --> fuel_price_decrease --> acceptability
```

Both sequences use a positive arrow, but they encode different mechanisms because direction is carried by the topic labels.

## DAG Syntax Operators

| Symbol | Name | Interpretation |
|---|---|---|
| `-->` | Positive causal link | `A --> B` means that A leads to B in the participant's reasoning. |
| `=` | Definition or equivalence | `A = B` means that the participant defines, frames, or understands A as B. |
| `;` | Distinct narrative path | Separates two distinct reasoning paths within the same answer. |
| `+` | Additive combination | `A + B` means that A and B form a combined package or bundle. |
| `&` | Coexistence | `A & B` means that A and B coexist without being additive components. |
| `<` | Priority or dominance | `A < B` means that B prevails over A. |
| `>` | Priority or dominance | `A > B` means that A prevails over B. |
| <code>&#124;</code> | Information source marker | `A --> B \| newspaper` records where the information came from. |

## Aggregated Topics

Parentheses attach subtopics to a broader concept:

```text
green_transport_development (electric_vehicle_infrastructure, soft_mobility)
```

Aggregated topics can appear inside longer sequences:

```text
alternative_policy = carbon_tax + green_transport_development (electric_vehicle_infrastructure, soft_mobility) --> acceptability
```

In the apps, the substantive subtopic selector is built only from subtopics already observed inside parentheses in existing coding columns. Coders can still paste or edit the full parentheses content when the current response requires a new or more precise subtopic.

## Scope Qualifiers

Square brackets indicate the actor, group, social position, or point of view to which a node applies:

```text
fuel_price_increase[others]
no_current_car_dependency[self]
potential_direct_impact[future_self]
```

Composite scopes are allowed:

```text
unreadiness[modest_household, company (agricultural_sector, sme)]
```

The outer square brackets attach the whole scope to the topic. Parentheses inside the scope describe subgroups.

In the apps, the scope selector is built only from scopes already observed inside square brackets in existing coding columns. Coders can still paste or edit the full square-bracket content when a new actor, group, or scoped subgroup is needed.

## Required Ending Nodes

For the paper, the app is prefilled with:

```text
acceptability
unacceptability
ambivalent_acceptability
```

These ending nodes can be enabled, disabled, or edited in the app sidebar. They are therefore project defaults rather than universal rules: researchers reusing the app should adapt the number and value of ending nodes to their own research question.

## Phase-Specific Coding Rules

### Top-of-Mind Phase

There is no required ending node. The coding should represent spontaneous associations, definitions, narrative paths, or information sources. When possible, sequences begin with:

```text
carbon_tax = ...
```

### Acceptability Phase

When analytically appropriate, the sequence should end with:

```text
acceptability
unacceptability
ambivalent_acceptability
```

Alternative or complementary policies can be introduced with:

```text
alternative_policy = ...
```

### Climate Anxiety Phase

The ending node should usually be the stated emotion or affective state. Mechanisms leading to that emotion appear before the emotional node.

### Final Phase

The sequence should synthesize the participant's final position while preserving the mechanism that explains it. When possible, it should end with `acceptability`, `unacceptability`, or `ambivalent_acceptability`.

## Cumulative Refinement Across Questions

Question-response pairs are not always treated as independent observations. When a question follows up on a previous answer, coders may reuse the previous relevant sequence as a backbone and refine it with new mechanisms, scope qualifiers, subtopics, or ending nodes.

This rule is applied only when the current response genuinely elaborates, qualifies, corrects, or deepens a previous line of reasoning. If the participant changes topic, rejects the previous framing, or adds no substantive information, the coding should reflect that shift. The code `none` is appropriate for explicitly non-substantive continuations.

## Validation Philosophy

The apps warn about likely syntax issues, such as repeated operators, unbalanced brackets, or standalone scope punctuation. These warnings do not block saving because final coding remains an interpretive qualitative act. They support consistency without replacing coder judgment.
