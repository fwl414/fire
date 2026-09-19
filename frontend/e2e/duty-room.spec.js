// 值班室：交接班与值班记录
//
// 此前这两个对话框的「保存」只弹一句「成功」、不发任何请求，表格里的列也对应不上库里的字段
// （记录「类型」恒为「日常值班」、「状态」是拿设备状态冒充；交接班「班次」恒为空、「当班接警」恒为 0）。
// 本文件固化「真的落库」与「列与字段一致」两条行为。
const { test, expect } = require('@playwright/test')
const { login, currentToken, apiPost } = require('./helpers')

/** 浏览器本地日期（与页面里的 todayDateStr 同一口径） */
async function localToday(page) {
  return page.evaluate(() => {
    const d = new Date()
    const pad = (n) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  })
}

async function apiGet(page, url, token) {
  return page.request.get(url, { headers: { Authorization: `Bearer ${token}` } })
}

/** 周排班表里「今天」是第几列（表头第一列是「班次」） */
async function todayColumnIndex(page) {
  const expected = await page.evaluate(() => {
    const d = new Date()
    const labels = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
    return `${labels[d.getDay()]} ${d.getMonth() + 1}/${d.getDate()}`
  })
  const headers = await page.locator('.schedule-table .el-table__header th .cell').allInnerTexts()
  return headers.findIndex(text => text.trim() === expected)
}

/** 清掉历史运行留下的排班：否则页面可能把「当前班次」判给上一轮的旧数据 */
async function removeLeftoverShifts(page, token) {
  const shifts = await (await apiGet(page, '/api/duty/shifts', token)).json()
  for (const shift of shifts) {
    if ((shift.shiftName || '').startsWith('E2E')) {
      await page.request.delete(`/api/duty/shifts/${shift.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
    }
  }
}

test.describe('值班室', () => {
  test('交接班与值班记录真的落库，且列与字段一致', async ({ page }) => {
    await login(page)
    const token = await currentToken(page)
    const today = await localToday(page)
    const stamp = Date.now()
    const shiftName = `E2E交接班-${stamp}`
    const personName = `E2E交班人${stamp}`
    const takeoverName = `E2E接班人${stamp}`
    const recordContent = `E2E值班记录-${stamp}`

    // 备一个今天生效、开始时间最早的排班：页面会把它当作「当前值班信息」
    await removeLeftoverShifts(page, token)
    const created = await apiPost(page, '/api/duty/shifts', {
      shift_name: shiftName,
      shift_type: 'day',
      start_time: '00:01',
      end_time: '23:59',
      duty_date: today,
      persons: [{ id: 1, name: personName, role: '值班员' }],
    }, token)
    expect(created.ok(), await created.text()).toBeTruthy()
    const shiftId = (await created.json()).shift.id

    await page.goto('/duty-room')
    await expect(page.locator('.shift-name')).toHaveText(shiftName, { timeout: 30_000 })
    await expect(page.locator('.duty-person .person-name').first()).toHaveText(personName)

    // ---------- 值班记录 ----------
    const beforeTotal = (await (await apiGet(page, '/api/duty/records?page_size=1', token)).json()).total

    await page.getByRole('button', { name: '新增记录' }).click()
    const logDialog = page.locator('.el-dialog').filter({ hasText: '新增值班记录' })
    await expect(logDialog).toBeVisible()

    // 新增时班次默认落在页面上正在显示的「当前值班信息」上，不是空的
    const shiftItem = logDialog.locator('.el-form-item').filter({ hasText: '班次' })
    await expect(shiftItem).toContainText(shiftName)
    // 班次下拉的候选来自真实排班，不是写死的班次名
    await shiftItem.locator('.el-select').click()
    await page.locator('.el-select-dropdown__item').filter({ hasText: shiftName }).first().click()

    // 值班人下拉的候选来自真实排班（当前班次的人），不是写死的名单
    const personItem = logDialog.locator('.el-form-item').filter({ hasText: '值班人' })
    await personItem.locator('.el-select').click()
    await page.locator('.el-select-dropdown__item').filter({ hasText: personName }).first().click()
    await logDialog.getByPlaceholder('请详细描述...').fill(recordContent)
    await logDialog.getByRole('button', { name: '保存记录' }).click()

    await expect(logDialog).toBeHidden({ timeout: 15_000 })
    const afterTotal = (await (await apiGet(page, '/api/duty/records?page_size=1', token)).json()).total
    expect(afterTotal, '保存后记录总数应 +1（说明真的落库了）').toBe(beforeTotal + 1)

    const saved = await (await apiGet(page, '/api/duty/records?page_size=100', token)).json()
    const record = saved.list.find(item => item.content === recordContent)
    expect(record, '新记录应出现在列表里').toBeTruthy()
    expect(record.dutyPerson).toBe(personName)
    expect(record.shiftName, '选了班次就应带上班次名').toBe(shiftName)

    // ---------- 交接班 ----------
    await page.getByRole('button', { name: '交接班' }).click()
    // 按「交班班次」定位：值班记录对话框里的班次下拉会显示「E2E交接班-*」，
    // 用「交接班」当关键词会同时命中两个对话框
    const handoverDialog = page.locator('.el-dialog').filter({ hasText: '交班班次' })
    await expect(handoverDialog).toBeVisible()
    await expect(handoverDialog, '交班人来自真实排班，不是写死的名单').toContainText(personName)

    await handoverDialog.locator('.el-select').click()
    // 没有人员主数据表：候选来自真实排班中的人，名单外的接班人直接输入
    await page.keyboard.type(takeoverName)
    await page.locator('.el-select-dropdown__item').filter({ hasText: takeoverName }).first().click()
    // 多选下拉选完不会自动收起，会盖住底部按钮：先按 Esc 收起，再提交
    await page.keyboard.press('Escape')
    await handoverDialog.getByRole('button', { name: '确认交接' }).click()
    await expect(handoverDialog).toBeHidden({ timeout: 15_000 })

    const handovers = await (await apiGet(page, '/api/duty/handovers?page_size=5', token)).json()
    const latest = handovers.list[0]
    expect(latest.fromPerson).toBe(personName)
    expect(latest.toPerson).toBe(takeoverName)
    expect(latest.shiftName, '交接班列表要带上班次名').toBe(shiftName)

    // 列表按交接时间倒序，最新一条应显示在表格首行
    await page.locator('.tab-item').filter({ hasText: '交接班记录' }).click()
    const firstRow = page.locator('.el-table__body-wrapper tbody tr').first()
    await expect(firstRow).toContainText(personName)
    await expect(firstRow).toContainText(takeoverName)
    await expect(firstRow).toContainText(shiftName)

    // ---------- 值班人员（只读，来自真实排班） ----------
    await page.locator('.tab-item').filter({ hasText: '值班人员' }).click()
    const personCard = page.locator('.person-card').filter({ hasText: personName })
    await expect(personCard).toBeVisible()
    await expect(personCard).toContainText(shiftName)
    // 改造前这里是写死的人员卡片（证书编号 / 电话 / 入职日期都是前端常量）
    await expect(personCard).not.toContainText('证书编号')

    // ---------- 周排班表（真实数据） ----------
    await page.locator('.tab-item').filter({ hasText: '值班排班' }).click()
    const scheduleRow = page.locator('.schedule-table tbody tr').filter({ hasText: shiftName })
    await expect(scheduleRow).toBeVisible()
    // 建的是今天 00:01-23:59 的班，必须落在「今天」这一列，而不是写死的那一周
    const todayColumn = await todayColumnIndex(page)
    expect(todayColumn, '周视图表头里应有一列是今天').toBeGreaterThan(-1)
    await expect(scheduleRow.locator('td').nth(todayColumn)).toContainText(personName)

    // 收尾：删掉这条排班，别让它成为后续用例的「当前班次」
    await page.request.delete(`/api/duty/shifts/${shiftId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
  })

  test('新增排班真的落库，并出现在对应那一周的表格里', async ({ page }) => {
    await login(page)
    const token = await currentToken(page)
    const today = await localToday(page)
    const stamp = Date.now()
    const shiftName = `E2E排班-${stamp}`
    const personName = `E2E值班员${stamp}`

    await removeLeftoverShifts(page, token)
    await page.goto('/duty-room')
    await page.locator('.tab-item').filter({ hasText: '值班排班' }).click()

    // 「新增排班」此前是个没有 handler 的空壳按钮
    await page.getByRole('button', { name: '新增排班' }).click()
    const dialog = page.locator('.el-dialog').filter({ hasText: '新增排班' })
    await expect(dialog).toBeVisible()
    // 默认排到今天：这样保存后正好落在当前显示的这一周里
    const dateItem = dialog.locator('.el-form-item').filter({ hasText: '值班日期' })
    await expect(dateItem.locator('input')).toHaveValue(today)

    await dialog.getByPlaceholder('如：白班 / 夜班').fill(shiftName)
    const personItem = dialog.locator('.el-form-item').filter({ hasText: '值班人员' })
    await personItem.locator('.el-select').click()
    await page.keyboard.type(personName)
    await page.locator('.el-select-dropdown__item').filter({ hasText: personName }).first().click()
    await page.keyboard.press('Escape')
    await dialog.getByRole('button', { name: '保存排班' }).click()

    await expect(dialog).toBeHidden({ timeout: 15_000 })
    const listed = await (await apiGet(page, `/api/duty/shifts?date=${today}`, token)).json()
    const created = listed.find(s => s.shiftName === shiftName)
    expect(created, '新排班应落库（此前按钮点了没有任何请求）').toBeTruthy()
    expect(created.dutyDate).toBe(today)
    expect(created.persons).toEqual([personName])
    expect(created.startTime).toBe('08:00')

    // 表格里同一行、今天那一列应出现这个人
    await page.locator('.tab-item').filter({ hasText: '值班排班' }).click()
    const row = page.locator('.schedule-table tbody tr').filter({ hasText: shiftName })
    await expect(row).toBeVisible()
    await expect(row.locator('td').nth(await todayColumnIndex(page))).toContainText(personName)

    await page.request.delete(`/api/duty/shifts/${created.id}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
  })
})
