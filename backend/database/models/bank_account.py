"""SHERLOCK — Stage A: BankAccount, plus Transaction.

Both unchanged from the legacy schema. Transaction is a judgment-call
addition — it's not in the handover's Phase A1 file list (only
`bank_account.py` is named), but the Financial Intelligence Agent
(backend/agents/financial/agent.py) directly queries `Transaction` and
the handover's own Golden Rule requires it to keep working unmodified, so
dropping this table was not an option.
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from backend.database.config import Base


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id = Column(Integer, primary_key=True)
    bank = Column(String, nullable=False)
    account_number = Column(String, nullable=False, unique=True)
    owner_id = Column(Integer, ForeignKey("persons.id"), nullable=False, index=True)
    is_flagged_mule = Column(Boolean, nullable=False, default=False, index=True)

    owner = relationship("Person", back_populates="bank_accounts")
    sent_transactions = relationship(
        "Transaction", foreign_keys="Transaction.sender_account_id", back_populates="sender_account"
    )
    received_transactions = relationship(
        "Transaction", foreign_keys="Transaction.receiver_account_id", back_populates="receiver_account"
    )

    def __repr__(self):
        return f"<BankAccount {self.account_number} @ {self.bank}>"


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    amount = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    sender_account_id = Column(Integer, ForeignKey("bank_accounts.id"), nullable=False, index=True)
    receiver_account_id = Column(Integer, ForeignKey("bank_accounts.id"), nullable=False, index=True)
    is_suspicious = Column(Boolean, nullable=False, default=False, index=True)

    sender_account = relationship(
        "BankAccount", foreign_keys=[sender_account_id], back_populates="sent_transactions"
    )
    receiver_account = relationship(
        "BankAccount", foreign_keys=[receiver_account_id], back_populates="received_transactions"
    )

    def __repr__(self):
        return f"<Transaction {self.amount} {self.sender_account_id}->{self.receiver_account_id}>"
