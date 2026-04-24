
# --- NEW CONTROL LAYER ---
from app.schemas import ScheduleShiftRequest, StaffAllocateRequest
from app.models import StaffMember, Shift

@app.post("/api/schedule/block/{block_id}/shift")
def shift_block(block_id: int, payload: ScheduleShiftRequest, session: Session = Depends(get_session)):
    block = session.get(ScheduleBlock, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")

    delta = timedelta(minutes=payload.minutes)
    block.starts_at += delta
    block.ends_at += delta
    session.add(block)

    # shift downstream blocks in same procedure chain
    blocks = session.exec(select(ScheduleBlock).where(ScheduleBlock.case_procedure_id == block.case_procedure_id).order_by(ScheduleBlock.starts_at)).all()
    found = False
    for b in blocks:
        if found:
            b.starts_at += delta
            b.ends_at += delta
            session.add(b)
        if b.id == block.id:
            found = True

    session.commit()
    return {"status": "shifted", "block_id": block.id}


@app.post("/api/staff/allocate")
def allocate_staff(payload: StaffAllocateRequest, session: Session = Depends(get_session)):
    block = session.get(ScheduleBlock, payload.schedule_block_id)
    staff = session.get(StaffMember, payload.staff_member_id)

    if not block or not staff:
        raise HTTPException(status_code=404, detail="Invalid block or staff")

    # availability check
    shifts = session.exec(select(Shift).where(Shift.staff_member_id == staff.id)).all()
    available = any(s.starts_at <= block.starts_at and s.ends_at >= block.ends_at for s in shifts)

    if not available:
        return {"status": "conflict", "detail": "Staff not available"}

    block.owner_role = staff.role
    session.add(block)
    session.commit()

    return {"status": "allocated", "staff": staff.name}
