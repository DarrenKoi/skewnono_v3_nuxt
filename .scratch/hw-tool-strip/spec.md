# H/W 관리 — 장비 선택 레일을 상단 가로 스트립으로

- Status: done (5ef644fd)
- Source: user request, 2026-08-25 16:25 KST, quoted verbatim below

## Request (verbatim)

> In the hardware page, we have tool selector in the left side. I think we have
> to move this component to be in the top component right below H/W 관리 status
> component so that we have more space to display 데일리 / 분기 component and
> data display. Can you manage the placement of components? as we move the tool
> selector component to the top and change the shape from vertical to the
> horizontal), we can show the models and based on the model selections, we may
> well see the tool lists.

## Requirements as read

1. The tool selector leaves the left rail and sits directly below the `H/W 관리`
   meta bar (`EbeamMetaBar`).
2. It becomes horizontal.
3. It shows the models; selecting a model narrows the tool list shown.
4. The 데일리 / 분기 tab bar and the data display below gain the freed width.
5. Existing behaviour of the page (tool selection driving the detail, search,
   On/Off filter, deep-link `eqp_id`) is preserved unless the request implies
   otherwise.
