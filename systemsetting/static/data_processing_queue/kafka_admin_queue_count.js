async function get_all_queues(queueListApiUrl) {
    try {
        const response = await fetch(queueListApiUrl);
        const result = await response.json();

        if (result.status === "SUCCESS" && result.data.success) {
            return result.data.queues; // Return the queue list
        } else {
            console.error("Failed to fetch queue list:", result.message);
            return [];
        }
    } catch (error) {
        console.error("Error fetching queue list:", error);
        return [];
    }
}

async function fetchQueueCount(queueName, apiUrl) {
    try {
        const response = await fetch(`${apiUrl}?queue_name=${queueName}`);
        const result = await response.json();
        if (result.status === "SUCCESS" && result.data.success) {
            return result.data.queues
        }
        return {} // Return queue count (default to 0 if not present)
    } catch (error) {
        console.error(`Error fetching queue count for ${queueName}:`, error);
        return 0;
    }
}


async function fetch_all_queue_counts(queue_list_url, queue_count_url) {
    try {
        // Step 1: Fetch all queues
        const queues = await get_all_queues(queue_list_url);

        // Step 2: Loop through each queue to fetch counts
        for (const queue of queues) {
            const response = await fetchQueueCount(queue.queue_name, queue_count_url);
            var res_queue_name = response.queue_name
            var res_queue_count = response.queue_count

            var res_failure_queue_name = response.failure_queue_name
            var res_failure_queue_count = response.failure_queue_count

            // Update the DOM or perform any action with the count
            const queue_count_id = document.getElementById(`queue-count-${res_queue_name}`);
            const failure_queue_count_id = document.getElementById(`queue-count-${res_failure_queue_name}`);
            if (queue_count_id) {
                queue_count_id.innerText = res_queue_count;
            }
            if (failure_queue_count_id) {
                failure_queue_count_id.innerText = res_failure_queue_count;
            }
        }

    } catch (error) {
        console.error("Failed to fetch queues:", error);
    }
}

document.addEventListener("DOMContentLoaded", function () {
    fetch_all_queue_counts(queue_list_url, queue_count_url);
});
