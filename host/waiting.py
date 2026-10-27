"""Recovery admission uses the same control, sources, implementation and grants."""
from modules.task_resource.waiting import Waiting
from control.policy.grants import GrantStore
from sdk.protocol import decode


def advance(core, schedule):
    def check(row,tx):
        core.gate.require_running()
        core._goal_memory_check(row['id'])
        body=decode(row['body']);bindings=decode(row['bindings'])
        for step in body['steps'][row['next_step']:]:
            cap=step['capability']
            core.registry.require(cap,bindings[cap])
            core.registry.require_context(cap,bindings[cap],body)
            GrantStore.authorize(tx,body,cap)
    Waiting(core.db).advance(check,schedule.enqueue)
