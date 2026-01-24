/**
 * Tab导航面板组件
 */

import { Activity, ChevronDown, ChevronUp } from 'lucide-react'

export default function TabPanel({
  result,
  activeTab,
  onTabChange,
  tabGroups,
  collapsedGroups,
  onToggleGroup
}) {
  if (!result || result.type !== 'ibdiagnet') {
    return (
      <aside className="tab-panel">
        <div className="tab-panel-placeholder">
          <p>上传 ibdiagnet 结果后即可浏览各类检查分组。</p>
        </div>
      </aside>
    )
  }

  return (
    <aside className="tab-panel">
      <div className="tab-panel-header">
        <div>
          <p className="tab-panel-caption">健康分组导航</p>
          <h3>分析标签</h3>
        </div>
      </div>

      <div className="tabs grouped-tabs">
        {/* Overview Tab */}
        <div
          className={`tab overview-tab ${activeTab === 'overview' ? 'active' : ''}`}
          onClick={() => onTabChange('overview')}
        >
          <Activity size={16} /> 总览
        </div>

        {/* Tab Groups */}
        {tabGroups.map(group => {
          const collapsed = !!collapsedGroups[group.key]
          return (
            <div key={group.key} className="tab-group">
              <div className="tab-group-header">
                <div>
                  <h4>{group.label}</h4>
                  <span>{group.description}</span>
                </div>
                <button
                  type="button"
                  className="tab-group-toggle"
                  onClick={() => onToggleGroup(group.key)}
                  aria-label="Toggle group"
                >
                  {collapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
                </button>
              </div>
              {!collapsed && (
                <div className="tab-group-tabs">
                  {group.tabs.map(({ key, label, icon: Icon }) => (
                    <div
                      key={key}
                      className={`tab ${activeTab === key ? 'active' : ''}`}
                      onClick={() => onTabChange(key)}
                    >
                      {Icon && <Icon size={16} />} {label}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </aside>
  )
}
