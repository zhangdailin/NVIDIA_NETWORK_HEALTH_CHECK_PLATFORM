import React from 'react';
import PropTypes from 'prop-types';
import './LogAnalysis.css';

const LogAnalysis = ({ data }) => {
  if (!data) return null;

  const { errors, warnings, routing_summary } = data;

  if (!errors?.length && !warnings?.length && !routing_summary?.length) {
    return (
      <div className="log-analysis-container empty">
        <p>No significant log events or routing issues found.</p>
      </div>
    );
  }

  return (
    <div className="log-analysis-container">
      <h3>Log Analysis & Routing Validation</h3>

      {/* Errors Section */}
      {errors && errors.length > 0 && (
        <div className="log-section error-section">
          <h4>
            <span className="icon">❌</span> Fabric Errors ({errors.length})
          </h4>
          <ul>
            {errors.map((err, idx) => (
              <li key={`err-${idx}`}>{err}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Warnings Section */}
      {warnings && warnings.length > 0 && (
        <div className="log-section warning-section">
          <h4>
            <span className="icon">⚠️</span> Warnings ({warnings.length})
          </h4>
          <ul>
            {warnings.map((warn, idx) => (
              <li key={`warn-${idx}`}>{warn}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Routing Summary Section */}
      {routing_summary && routing_summary.length > 0 && (
        <div className="log-section routing-section">
          <h4>
            <span className="icon">🔄</span> Routing Validation Report
          </h4>
          <div className="routing-content">
            {routing_summary.map((line, idx) => (
              <div key={`route-${idx}`} className="log-line">
                {line}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

LogAnalysis.propTypes = {
  data: PropTypes.shape({
    errors: PropTypes.arrayOf(PropTypes.string),
    warnings: PropTypes.arrayOf(PropTypes.string),
    routing_summary: PropTypes.arrayOf(PropTypes.string),
    log_path: PropTypes.string,
    error: PropTypes.string,
  }),
};

LogAnalysis.defaultProps = {
  data: null,
};

export default LogAnalysis;
