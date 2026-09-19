export function riskTagType(level = "") {
  if (level.includes("严重")) return "danger"
  if (level.includes("高")) return "danger"
  if (level.includes("中")) return "warning"
  if (level.includes("低")) return "success"
  return "info"
}

export function riskColor(level = "") {
  if (level.includes("严重")) return "#8B0000"
  if (level.includes("高")) return "#F56C6C"
  if (level.includes("中")) return "#E6A23C"
  if (level.includes("低")) return "#67C23A"
  return "#909399"
}

export function riskBg(level = "") {
  if (level.includes("严重")) return "#fff1f2"
  if (level.includes("高")) return "#fef2f2"
  if (level.includes("中")) return "#fffbeb"
  if (level.includes("低")) return "#f0f9eb"
  return "#f4f4f5"
}
