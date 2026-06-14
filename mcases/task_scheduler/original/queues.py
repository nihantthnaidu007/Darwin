"""Priority bucket queue with index and size mirrors."""


class PriorityBuckets:
    def __init__(self):
        self.buckets = {}
        self.index = {}
        self.total = 0

    def push(self, job_id, priority):
        if priority not in self.buckets:
            self.buckets[priority] = []
        self.buckets[priority].append(job_id)
        self.index[job_id] = priority
        self.total = self.total + 1
        return self.total

    def pop_best(self):
        if self.total == 0:
            return None
        ordered_priorities = sorted(self.buckets.keys())
        ordered_priorities.reverse()
        for priority in ordered_priorities:
            bucket = self.buckets[priority]
            if len(bucket) > 0:
                job_id = bucket[0]
                del bucket[0]
                del self.index[job_id]
                self.total = self.total - 1
                return job_id
        return None

    def remove(self, job_id):
        if job_id not in self.index:
            return False
        priority = self.index[job_id]
        bucket = self.buckets.get(priority, [])
        position = -1
        for i in range(len(bucket)):
            if bucket[i] == job_id:
                position = i
                break
        if position >= 0:
            del bucket[position]
            del self.index[job_id]
            self.total = self.total - 1
            return True
        return False

    def snapshot(self):
        ordered_priorities = sorted(self.buckets.keys())
        ordered_priorities.reverse()
        result = []
        for priority in ordered_priorities:
            for job_id in self.buckets[priority]:
                result.append(job_id)
        return result

    def count(self):
        return self.total
