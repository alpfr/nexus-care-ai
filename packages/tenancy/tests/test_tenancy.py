"""Tests for the tenancy package."""

import asyncio

import pytest

from nexus_care_tenancy import (
    PHIWriteForbiddenError,
    TenantNotSetError,
    TenantState,
    assert_can_write,
    assert_can_write_phi,
    clear_tenant_context,
    current_tenant,
    current_tenant_id,
    set_tenant_context,
)


@pytest.fixture(autouse=True)
def clear_ctx_between_tests():
    """Ensure each test starts with no tenant context set."""
    clear_tenant_context()
    yield
    clear_tenant_context()


class TestTenantContext:
    def test_set_and_read(self):
        ctx = set_tenant_context(
            tenant_id=42, state=TenantState.ACTIVE, region_code="us-central"
        )
        assert ctx.tenant_id == 42
        assert ctx.state is TenantState.ACTIVE
        assert ctx.region_code == "us-central"
        assert current_tenant().tenant_id == 42
        assert current_tenant_id() == 42

    def test_unset_raises(self):
        with pytest.raises(TenantNotSetError):
            current_tenant()

    def test_clear(self):
        set_tenant_context(tenant_id=1, state=TenantState.ACTIVE, region_code="us-central")
        clear_tenant_context()
        with pytest.raises(TenantNotSetError):
            current_tenant()

    def test_can_write_phi_only_when_active(self):
        for state, expected in [
            (TenantState.SANDBOX, False),
            (TenantState.PENDING_ACTIVATION, False),
            (TenantState.ACTIVE, True),
            (TenantState.SUSPENDED, False),
            (TenantState.TERMINATED, False),
        ]:
            ctx = set_tenant_context(tenant_id=1, state=state, region_code="us-central")
            assert ctx.can_write_phi is expected, f"{state}: expected can_write_phi={expected}"

    def test_is_readonly(self):
        for state, expected in [
            (TenantState.SANDBOX, False),
            (TenantState.PENDING_ACTIVATION, False),
            (TenantState.ACTIVE, False),
            (TenantState.SUSPENDED, True),
            (TenantState.TERMINATED, True),
        ]:
            ctx = set_tenant_context(tenant_id=1, state=state, region_code="us-central")
            assert ctx.is_readonly is expected, f"{state}: expected is_readonly={expected}"


class TestPHIWriteGuards:
    def test_active_tenant_allowed(self):
        set_tenant_context(tenant_id=1, state=TenantState.ACTIVE, region_code="us-central")
        # Should not raise
        assert_can_write_phi()
        assert_can_write()

    def test_sandbox_blocked_from_phi(self):
        set_tenant_context(tenant_id=1, state=TenantState.SANDBOX, region_code="us-central")
        with pytest.raises(PHIWriteForbiddenError, match="sandbox"):
            assert_can_write_phi()
        # But non-PHI writes are allowed in sandbox
        assert_can_write()

    def test_pending_activation_blocked_from_phi(self):
        set_tenant_context(
            tenant_id=1, state=TenantState.PENDING_ACTIVATION, region_code="us-central"
        )
        with pytest.raises(PHIWriteForbiddenError):
            assert_can_write_phi()
        assert_can_write()

    def test_suspended_blocks_all_writes(self):
        set_tenant_context(tenant_id=1, state=TenantState.SUSPENDED, region_code="us-central")
        with pytest.raises(PHIWriteForbiddenError):
            assert_can_write_phi()
        with pytest.raises(PermissionError):
            assert_can_write()

    def test_terminated_blocks_all_writes(self):
        set_tenant_context(tenant_id=1, state=TenantState.TERMINATED, region_code="us-central")
        with pytest.raises(PHIWriteForbiddenError):
            assert_can_write_phi()
        with pytest.raises(PermissionError):
            assert_can_write()

    def test_no_tenant_blocks(self):
        with pytest.raises(TenantNotSetError):
            assert_can_write_phi()
        with pytest.raises(TenantNotSetError):
            assert_can_write()


class TestAsyncIsolation:
    """Critical: prove that two concurrent tasks see their own tenant context.

    This is the property that makes the whole multi-tenancy model safe under
    asyncio concurrency. If ContextVar leaked across tasks, tenant A's request
    could read tenant B's data. Test this exhaustively.
    """

    async def test_two_tasks_see_distinct_tenants(self):
        results: dict[int, int] = {}

        async def task(task_id: int, tenant_id: int) -> None:
            set_tenant_context(
                tenant_id=tenant_id, state=TenantState.ACTIVE, region_code="us-central"
            )
            # Yield to the event loop to maximize chance of cross-contamination
            await asyncio.sleep(0)
            results[task_id] = current_tenant_id()

        await asyncio.gather(task(1, 100), task(2, 200), task(3, 300))
        assert results == {1: 100, 2: 200, 3: 300}

    async def test_unset_in_one_task_does_not_affect_other(self):
        a_value = []
        b_value = []
        b_started = asyncio.Event()
        a_can_finish = asyncio.Event()

        async def task_a():
            set_tenant_context(tenant_id=1, state=TenantState.ACTIVE, region_code="us-central")
            await b_started.wait()
            # B has cleared its context; A should still see its own
            await asyncio.sleep(0)
            a_value.append(current_tenant_id())
            a_can_finish.set()

        async def task_b():
            set_tenant_context(tenant_id=2, state=TenantState.ACTIVE, region_code="us-central")
            b_value.append(current_tenant_id())
            clear_tenant_context()
            b_started.set()
            await a_can_finish.wait()

        await asyncio.gather(task_a(), task_b())
        assert a_value == [1]
        assert b_value == [2]
