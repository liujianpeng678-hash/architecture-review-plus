---
name: math-new-lesson-v2
description: Create or revise Chinese mathematics new-lesson Word materials using the Skill V2 hierarchy, progressive problem chains, paired question and analysis papers, and evidence-based diagrams when they improve understanding or solving.
---

# Math New Lesson V2

Use this skill for Chinese mathematics new-lesson materials in Word or equivalent lesson artifacts.

## Required hierarchy

Organize every lesson as:

```text
章节
└── 知识点
    ├── 知识来源
    ├── 知识形成
    ├── 核心公式
    └── 问题
        └── 进化链
            └── 节点
```

A problem title names the task directly, such as `求圆的方程`, `求单调性`, `判断函数是否单调`, `证明函数单调性`, or `求参数范围`. Avoid titles such as “如何求……”.

### Atomic-problem gate

Every problem must be an executable atomic task written as **action + one mathematical object or property**, for example `求圆心`, `求半径`, `求单调性`, `求最值`, `求参数`, `求切线方程`, `证明垂直`, or `求距离`.

Do not use umbrella titles that contain several sub-tasks, such as `求圆的几何信息`, `研究圆的性质`, `函数综合问题`, or `圆的综合应用`. If a draft problem contains multiple outputs (for example, center + radius + point position), split it into separate problems before designing chains.

## Problem and chain rules

- One problem contains chains that solve the same core task. Chains may change the given conditions, representation, requested output, or question form, but they must keep the core task stable.
- **Same-source gate:** all chains under one problem must keep the same core mathematical object or property. Different chains may use different representations, entry conditions, or methods, but they may not silently switch from center to radius, from radius to position relation, or from monotonicity to extrema.
- Within one chain, each later node must be derived from the previous node by retaining its method and adding or tightening a condition, output requirement, or verification requirement. A student who can solve a later node should be able to solve every earlier node in that chain.
- Acceptable question-form changes include a direct calculation becoming a judgment question, proof question, or parameter or parameter-range question when the underlying task remains the same.
- A node may change from direct calculation to judgment, proof, parameter, or parameter-range form only when the researched object/property stays fixed. For example, `求半径 → 判断半径是否大于 3 → 证明半径大于 3 → 求使半径大于 3 的参数范围` is one valid chain; `求圆心 → 求半径` is a problem boundary and must be split.
- Every node includes: 进化过程, 一句话最优解法, 解题步骤, 例题, and a five-line student answer area. The analysis paper expands the solution one step per line.
- Similar questions keep the same wording and structure as the node example, changing only two main data values. Similar questions include an answer area and do not include an extra evolution section or solution-step section.

## Paired papers

Every version must contain both:

1. 题目卷: prompts, diagrams, and student answer areas.
2. 解析卷: the same structure with detailed one-step-per-line analysis and answers.

This applies to student class, teacher class, homework, and review versions. Homework changes the data while preserving the problem and chain structure. Review keeps the final model of each chain.

## Diagram rule

When a knowledge point or node question needs a diagram to understand the concept, translate the conditions, build the model, or solve the problem, include a diagram. Do not leave a needed diagram as a text-only description.

- Use a clear, labeled diagram with only the elements needed for the task.
- Keep the diagram aligned with the exact data in the question, including coordinates, points, lines, regions, arrows, and labels.
- Place the diagram next to or immediately after the relevant knowledge point or node question.
- Repeat or preserve the same diagram in the analysis paper so the explanation refers to the same visual model.
- For changed-data homework questions, regenerate or update the diagram so it matches the new data.
- Do not add decorative images when a diagram does not improve understanding or solving.

## Quality check

Before delivery, verify the heading hierarchy, problem and chain consistency, data changes in similar questions and homework, diagram-to-question consistency, paired question and analysis papers, and the final rendered pagination.

## Confirmed final format

Use this as the default structure for future Chinese mathematics new-lesson materials:

```text
章节
└── 知识点
    ├── 知识来源
    ├── 知识形成
    ├── 核心公式
    ├── 问题1：求圆的方程
    │   └── 进化链 → 节点
    ├── 问题2：求圆心
    │   └── 进化链 → 节点
    ├── 问题3：求半径
    │   └── 进化链 → 节点
    ├── 问题4：判断点与圆的位置关系
    │   └── 进化链 → 节点
    └── 问题5：判断直线与圆的位置关系
        └── 进化链 → 节点
```

The last four problem names are a circle-lesson example of the atomic-problem rule, not a fixed list for every topic. For another knowledge point, replace them with its own smallest executable tasks, such as `求单调性`, `求最值`, `求参数`, `求切线方程`, `证明垂直`, or `求距离`.

For every problem, keep both a question paper and an analysis paper. Each node contains `进化过程`, `一句话最优解法`, `解题步骤`, `例题`, and a five-line answer area. The analysis paper gives the node solution one step per line. Teacher-version similar questions keep the node's wording and task form, change the main data, include an answer area, and do not add an evolution section or solution-step section. Use diagrams wherever the knowledge point or node genuinely needs a visual model, and keep the question-paper and analysis-paper diagrams synchronized.
