from pathlib import Path
import subprocess


APP_JS = Path(__file__).resolve().parents[1] / "static" / "app.js"


def run_node(script: str) -> str:
    result = subprocess.run(
        ["node", "-e", script],
        cwd=APP_JS.parents[1],
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def test_model_entry_preview_formats_expense_as_chinese_text_without_json_payload():
    script = r'''
const fs = require('fs');
const vm = require('vm');
const code = fs.readFileSync('static/app.js', 'utf8');
const context = {
  console,
  document: { body: { dataset: {} }, querySelector: () => null, querySelectorAll: () => [] },
  window: { location: { search: '' }, setInterval: () => null },
  URLSearchParams,
  Date,
};
vm.createContext(context);
vm.runInContext(code, context);
const text = context.formatModelOperationPreview({
  type: 'add_expense',
  label: '新增支出：午餐 ¥168',
  payload: { day_id: 'day1', category: '午餐', title: '午餐', amount: 168, notes: '扫码支付' }
}, 0);
if (!text.includes('1. 新增支出：午餐 ¥168')) throw new Error(text);
if (!text.includes('类别：午餐')) throw new Error(text);
if (!text.includes('金额：¥168')) throw new Error(text);
if (!text.includes('备注：扫码支付')) throw new Error(text);
if (text.includes('{') || text.includes('"amount"')) throw new Error(text);
console.log(text);
'''
    output = run_node(script)
    assert "新增支出" in output


def test_model_entry_preview_formats_booking_as_chinese_text_without_json_payload():
    script = r'''
const fs = require('fs');
const vm = require('vm');
const code = fs.readFileSync('static/app.js', 'utf8');
const context = {
  console,
  document: { body: { dataset: {} }, querySelector: () => null, querySelectorAll: () => [] },
  window: { location: { search: '' }, setInterval: () => null },
  URLSearchParams,
  Date,
};
vm.createContext(context);
vm.runInContext(code, context);
const text = context.formatModelOperationPreview({
  type: 'add_booking',
  label: '新增预订：明宇丽呈酒店',
  payload: { day_id: 'day2', type: '酒店', name: '明宇丽呈酒店', status: '已预订', price: 398, notes: '可免费取消' }
}, 0);
if (!text.includes('1. 新增预订：明宇丽呈酒店')) throw new Error(text);
if (!text.includes('类型：酒店')) throw new Error(text);
if (!text.includes('状态：已预订')) throw new Error(text);
if (!text.includes('价格：¥398')) throw new Error(text);
if (!text.includes('备注：可免费取消')) throw new Error(text);
if (text.includes('{') || text.includes('"price"')) throw new Error(text);
console.log(text);
'''
    output = run_node(script)
    assert "新增预订" in output


def test_ai_update_previews_are_chinese_text_without_json_payload():
    script = r'''
const fs = require('fs');
const vm = require('vm');
const code = fs.readFileSync('static/app.js', 'utf8');
const context = {
  console,
  document: { body: { dataset: {} }, querySelector: () => null, querySelectorAll: () => [] },
  window: { location: { search: '' }, setInterval: () => null },
  URLSearchParams,
  Date,
};
vm.createContext(context);
vm.runInContext(code, context);
const operations = [
  { type: 'update_booking', label: '修改预订：booking-1', payload: { booking_id: 'booking-1', changes: { status: '已确认', price: 188, notes: '电话确认' } } },
  { type: 'update_supply', label: '修改采购：s-1', payload: { supply_id: 's-1', changes: { status: '不买', quantity: '0' } } },
  { type: 'update_itinerary', label: '修改行程：day1 / next_action', payload: { day_id: 'day1', field: 'next_action', value: '先去酒店办理入住' } },
];
const text = operations.map((op, index) => context.formatModelOperationPreview(op, index)).join('\n\n');
if (!text.includes('预订ID：booking-1')) throw new Error(text);
if (!text.includes('状态：已确认')) throw new Error(text);
if (!text.includes('物资ID：s-1')) throw new Error(text);
if (!text.includes('数量：0')) throw new Error(text);
if (!text.includes('字段：next_action')) throw new Error(text);
if (!text.includes('内容：先去酒店办理入住')) throw new Error(text);
if (text.includes('{') || text.includes('"changes"')) throw new Error(text);
console.log(text);
'''
    output = run_node(script)
    assert "预订ID" in output
