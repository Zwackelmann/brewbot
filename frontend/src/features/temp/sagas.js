import { call, put, takeEvery } from 'redux-saga/effects';
import axios from 'axios';
import api from '../../app/api';
import { tempActions } from './slice';

function* fetchTempSaga() {
  try {
    const response = yield call(api.temp);
    if (response.status === 'success') {
      yield put(tempActions.fetchSuccess(response.data));
    } else if (response.status === 'error') {
      yield put(tempActions.fetchFailure(response.error));
    }
  } catch (error) {
    yield put(tempActions.fetchFailure(error.message));
  }
}

export function* watchFetchTemp() {
  yield takeEvery(tempActions.fetchRequest.type, fetchTempSaga);
}

