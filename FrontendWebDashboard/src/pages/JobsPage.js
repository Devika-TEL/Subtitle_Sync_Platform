import React, { useEffect, useState } from "react";
import { getJobs } from "../services/api";
import ProgressTracker from "../components/ProgressTracker";
import Notification from "../components/Notification";

/**
 * JobsPage shows user's current processing jobs and statuses.
 */
function JobsPage() {
  const [jobs, setJobs] = useState([]);
  const [error, setError] = useState("");
  
  // Poll for jobs every 8 seconds
  useEffect(() => {
    let running = true;
    async function fetchJobs() {
      try {
        const data = await getJobs();
        if (running) setJobs(data);
      } catch (e) {
        setError(e.message || "Failed to fetch jobs");
      }
    }
    fetchJobs();
    const interval = setInterval(fetchJobs, 8000);
    return () => { running = false; clearInterval(interval); };
  }, []);

  return (
    <section>
      <h2>Processing Jobs</h2>
      {error && <Notification type="error" message={error} />}
      <ProgressTracker jobs={jobs || []} />
    </section>
  );
}

export default JobsPage;
