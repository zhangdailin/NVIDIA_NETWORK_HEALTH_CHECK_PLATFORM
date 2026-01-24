/**
 * 全局加载遮罩组件
 */

export default function LoadingOverlay({ uploadProgress = 0 }) {
  const isUploading = uploadProgress > 0 && uploadProgress < 100

  return (
    <div className="loading-overlay">
      <div className="spinner"></div>
      {isUploading ? (
        <>
          <p>正在上传文件... 请稍候。</p>
          <div style={{ marginTop: '20px', width: '300px' }}>
            <div style={{
              width: '100%',
              height: '8px',
              backgroundColor: 'rgba(255,255,255,0.2)',
              borderRadius: '4px',
              overflow: 'hidden'
            }}>
              <div style={{
                width: `${uploadProgress}%`,
                height: '100%',
                backgroundColor: '#76b900',
                transition: 'width 0.3s ease'
              }} />
            </div>
            <p style={{ marginTop: '10px', fontSize: '0.9rem' }}>
              进度: {uploadProgress}%
            </p>
          </div>
        </>
      ) : (
        <>
          <p>正在处理分析... 大文件可能需要几分钟。</p>
          <p style={{ marginTop: '10px', fontSize: '0.85rem', opacity: 0.8 }}>
            请耐心等待。后端正在分析网络数据。
          </p>
        </>
      )}
    </div>
  )
}
