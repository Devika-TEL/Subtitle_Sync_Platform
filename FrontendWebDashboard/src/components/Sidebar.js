import React from "react";
import { NavLink } from "react-router-dom";

/** PUBLIC_INTERFACE
 * Sidebar component for navigation. Adjusts items based on user role.
 * @param {string} role - 'user' | 'admin'
 */
function Sidebar({ role = "user" }) {
  return (
    <nav className="sidebar" aria-label="Main Navigation">
      <ul>
        <li>
          <NavLink to="/" end>Home</NavLink>
        </li>
        <li>
          <NavLink to="/upload">Upload Video/Subtitles</NavLink>
        </li>
        <li>
          <NavLink to="/jobs">Monitor Processing</NavLink>
        </li>
        <li>
          <NavLink to="/subtitles">Subtitle Management</NavLink>
        </li>
        {(role === "admin") && (
          <>
            <li>
              <NavLink to="/admin/system">System Monitor</NavLink>
            </li>
            <li>
              <NavLink to="/admin/compliance">Compliance Reports</NavLink>
            </li>
          </>
        )}
      </ul>
    </nav>
  );
}

export default Sidebar;
