import { Moon, Sun } from 'lucide-react'
import { useTheme } from '../contexts/ThemeContext'
import './ThemeToggle.css'

const ThemeToggle = () => {
  const { theme, toggleTheme, isDark } = useTheme()

  return (
    <button
      className="theme-toggle"
      onClick={toggleTheme}
      aria-label={`切换到${isDark ? '浅色' : '深色'}主题`}
      title={`切换到${isDark ? '浅色' : '深色'}主题`}
    >
      <div className="theme-toggle-icon">
        {isDark ? (
          <Sun size={20} className="theme-icon sun" />
        ) : (
          <Moon size={20} className="theme-icon moon" />
        )}
      </div>
      <span className="theme-toggle-label">
        {isDark ? '浅色' : '深色'}
      </span>
    </button>
  )
}

export default ThemeToggle
