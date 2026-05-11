# 旅行执行网站 API

所有接口返回 JSON。写入接口会直接修改 `data/trip.json`，外部模型如果需要“先预览再确认”，应先生成 proposal，再调用 `POST /api/confirm-change`。

## 行程

- `GET /api/trip`：获取完整旅行数据
- `GET /api/days`：获取所有行程日
- `GET /api/days/<day_id>`：获取单日详情、当天预算和已记账总额
- `POST /api/days/<day_id>`：更新单日字段
- `POST /api/days/<day_id>/timeline`：新增一条时间线

更新单日字段示例：

```json
{
  "next_action": "先去加油，再出发去赛里木湖",
  "risks": ["当天大风则减少湖边停留"]
}
```

新增时间线示例：

```json
{
  "time": "16:00-16:30",
  "title": "临时补给",
  "detail": "买水和咖啡"
}
```

## 账本

- `GET /api/expenses`：获取全部支出
- `GET /api/expenses?day_id=day1`：获取某天支出
- `POST /api/expenses`：新增支出
- `GET /api/expenses/<expense_id>`：获取单笔支出
- `PUT /api/expenses/<expense_id>` 或 `POST /api/expenses/<expense_id>`：更新支出
- `DELETE /api/expenses/<expense_id>` 或 `POST /api/expenses/<expense_id>/delete`：删除支出

新增支出示例：

```json
{
  "day_id": "day1",
  "category": "过路费",
  "title": "过路费",
  "amount": 200,
  "notes": "模型解析：过路费200"
}
```

## 预订

- `GET /api/bookings`：获取全部预订
- `GET /api/bookings?day_id=day1`：获取某天预订
- `POST /api/bookings`：新增预订
- `GET /api/bookings/<booking_id>`：获取单条预订
- `PUT /api/bookings/<booking_id>` 或 `POST /api/bookings/<booking_id>`：更新预订
- `DELETE /api/bookings/<booking_id>` 或 `POST /api/bookings/<booking_id>/delete`：删除预订

新增预订示例：

```json
{
  "day_id": "day1",
  "type": "酒店",
  "name": "奎屯明宇丽呈酒店",
  "status": "已预订",
  "price": 320,
  "notes": "携程，可免费取消"
}
```

可用状态：`待定`、`待确认`、`已预订`、`已确认`、`取消`。也支持英文别名：`pending`、`need_confirm`、`reserved` / `booked`、`confirmed`、`cancelled` / `canceled`。

## 采购

- `GET /api/supplies`：获取采购清单
- `GET /api/supplies?status=待购买`：按状态过滤
- `POST /api/supplies`：新增采购项
- `GET /api/supplies/<supply_id>`：获取单个采购项
- `PUT /api/supplies/<supply_id>` 或 `POST /api/supplies/<supply_id>`：更新采购项
- `DELETE /api/supplies/<supply_id>` 或 `POST /api/supplies/<supply_id>/delete`：删除采购项

新增采购示例：

```json
{
  "name": "矿泉水",
  "quantity": "1 箱",
  "category": "饮水",
  "status": "待购买"
}
```

可用状态：`待购买`、`已购买`、`不买`、`备用`。也支持英文别名：`todo` / `pending`、`bought` / `purchased`、`skip`、`backup`。

## 模型解析与确认

- `POST /api/ai/parse-entry`：网页用的模型解析入口，支持 `multipart/form-data`
- `POST /api/ai/propose`：通用 AI tools 变更预览
- `POST /api/confirm-change`：确认 proposal 并写入

确认写入示例：

```json
{
  "proposal": {
    "operations": [
      {
        "type": "add_expense",
        "label": "新增支出：过路费 ¥200",
        "payload": {
          "day_id": "day1",
          "category": "过路费",
          "title": "过路费",
          "amount": 200,
          "notes": "外部模型解析"
        }
      }
    ]
  }
}
```

支持的 operation：

- `add_expense`
- `add_booking`
- `update_booking`
- `update_supply`
- `update_itinerary`
