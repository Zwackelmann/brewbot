import { call, put, takeEvery } from 'redux-saga/effects';
import axios from 'axios';
import api from '../../app/api';
import { motorActions } from './slice';

function* sendMotorCmdSaga(relayStateAction) {
  try {
    const response = yield call(api.motorCmd(relayStateAction.payload));
    if (response.status === 'success') {
      yield put(motorActions.cmdSuccess(response.data));
    } else if (response.status === 'error') {
      yield put(motorActions.cmdFailure(response.error));
    }
  } catch (error) {
    yield put(motorActions.cmdFailure(error.message));
  }
}

function* fetchMotorStateSaga() {
  try {
    const response = yield call(api.motorState);
    if (response.status === 'success') {
      yield put(motorActions.fetchSuccess(response.data));
    } else if (response.status === 'error') {
      yield put(motorActions.fetchFailure(response.error));
    }
  } catch (error) {
    yield put(motorActions.fetchFailure(error.message));
  }
}

export function* watchSendMotorCmd() {
  yield takeEvery(motorActions.sendCmd.type, sendMotorCmdSaga);
}

export function* watchFetchMotorState() {
  yield takeEvery(motorActions.fetchState.type, fetchMotorStateSaga);
}
