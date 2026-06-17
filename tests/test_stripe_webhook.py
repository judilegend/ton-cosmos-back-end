import pytest
import stripe
from fastapi import status
from unittest.mock import AsyncMock, patch

STRIPE_WEBHOOK_PAYLOAD = {
    "id": "evt_test_123",
    "object": "event",
    "type": "checkout.session.completed",
    "data": {
        "object": {
            "id": "cs_test_999",
            "payment_status": "paid",
            "metadata": {
                "order_id": "42"
            }
        }
    }
}

WEBHOOK_URL = "/api/v1/stripe/webhook"


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.stripe.stripe.Webhook.construct_event")
@patch("app.api.v1.endpoints.stripe.process_order_pipeline")
async def test_webhook_stripe_success(mock_pipeline, mock_stripe_verify, client):
    mock_stripe_verify.return_value = STRIPE_WEBHOOK_PAYLOAD
    mock_pipeline.return_value = None

    headers = {"stripe-signature": "t=123,v1=valid_signature_mock"}
    
    response = await client.post(WEBHOOK_URL, json=STRIPE_WEBHOOK_PAYLOAD, headers=headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.text == "Webhook processed"
    
    mock_pipeline.assert_called_once_with(42, "cs_test_999", False)


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.stripe.stripe.Webhook.construct_event")
async def test_webhook_stripe_invalid_signature(mock_stripe_verify, client):
    mock_stripe_verify.side_effect = stripe.error.SignatureVerificationError("Signature invalide", "sig_header")

    headers = {"stripe-signature": "t=123,v1=HACKER_SIG"}
    response = await client.post(WEBHOOK_URL, json=STRIPE_WEBHOOK_PAYLOAD, headers=headers)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid signature" in response.text


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.stripe.stripe.Webhook.construct_event")
@patch("app.api.v1.endpoints.stripe.process_order_pipeline")
async def test_webhook_stripe_order_not_found(mock_pipeline, mock_stripe_verify, client):
    payload_wrong_order = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_999",
                "payment_status": "paid",
                "metadata": {"order_id": "999999"}
            }
        }
    }
    mock_stripe_verify.return_value = payload_wrong_order
    mock_pipeline.return_value = None

    headers = {"stripe-signature": "t=123,v1=valid_signature_mock"}
    response = await client.post(WEBHOOK_URL, json=payload_wrong_order, headers=headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.text == "Webhook processed"
    
    mock_pipeline.assert_called_once_with(999999, "cs_test_999", False)