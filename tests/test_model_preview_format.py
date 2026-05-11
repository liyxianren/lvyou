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
